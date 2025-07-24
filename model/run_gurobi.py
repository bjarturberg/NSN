import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Activity, Area, Session as DbSession, Conflict, Prerequisite
import gurobipy as gp
from gurobipy import GRB

# --- Connect to DB ---
engine = create_engine('sqlite:///sports_schedule.db')
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

# --- Read Data from DB ---
activities = db.query(Activity).all()
E = [a.activity_id for a in activities]

D = ['sun', 'mán', 'þri', 'mið', 'fim', 'fös', 'lau']
Dw = ['sun', 'lau']
areas = db.query(Area).all()
A = [a.area_id for a in areas]

db_sessions = db.query(DbSession).all()

# e_a: which areas are allowed for each activity
e_a = {}
for s in db_sessions:
    e_a.setdefault(s.activity_id, set()).add(s.area_id)

# class_schedule: for each activity, which days have what time ranges
class_schedule = {}
for s in db_sessions:
    class_schedule.setdefault(s.activity_id, {})[s.day_of_week] = (s.min_start, s.max_end)

# number_exercises: lengths and group counts
number_exercises = {}
for a in activities:
    l_str = a.length_str or ''
    l_wknd_str = a.length_weekend_str or ''
    lengd = [float(x.strip()) for x in l_str.split(',') if x.strip()] if l_str else []
    lengd_helgar = [float(x.strip()) for x in l_wknd_str.split(',') if x.strip()] if l_wknd_str else []
    number_exercises[a.activity_id] = [lengd, lengd_helgar, a.groups_count or 1]

# EXsubset and DXsubset
EXsubset = {}
DXsubset = {}
for e in E:
    EXsubset[e] = [e + " - " + str(i+1) for i in range(len(number_exercises[e][0]))] + \
                  [e + " * " + str(i+1) for i in range(len(number_exercises[e][1]))]
    DXsubset[e] = [dx*number_exercises[e][2] for dx in number_exercises[e][0]] + \
                  [dx*number_exercises[e][2] for dx in number_exercises[e][1]]
EX = [item for sublist in EXsubset.values() for item in sublist]
DX_values = [value for sublist in DXsubset.values() for value in sublist]
DX = dict(zip(EX, DX_values))

# --- Build EDA, UB, LB, CX ---
EDA = []
UB = {}
LB = {}
CX = {}
for e in E:
    for d in D:
        for a_ in e_a.get(e, []):
            if d in class_schedule[e].keys():
                for ex in EXsubset[e]:
                    if d in Dw and '*' in ex:
                        EDA.append((ex, d, a_))
                    if d not in Dw and '*' not in ex:
                        EDA.append((ex, d, a_))
                    ub_val = class_schedule[e][d][1]
                    lb_val = class_schedule[e][d][0]
                    if ub_val is None:
                        ub_val = 24*60  # or another max value
                    if lb_val is None:
                        lb_val = 0
                    UB[(ex, d, a_)] = float(ub_val)
                    LB[(ex, d, a_)] = float(lb_val)

# Conflicts (build CX mapping each activity to conflicting activity subsessions)
conflict_dict = {}
conflicts = db.query(Conflict).all()
for c in conflicts:
    conflict_dict.setdefault(c.activity_id, []).append(c.conflict_activity_id)
for e in E:
    if e in conflict_dict.keys():
        tmp = [EXsubset[e_] for e_ in conflict_dict[e] if e_ in EXsubset.keys()]
        if len(tmp) > 0:
            CX[e] = tmp[0]

# Precedence (fyrir/undan)
undan_eftir = {}
prereqs = db.query(Prerequisite).all()
for p in prereqs:
    undan_eftir[p.activity_id] = p.must_be_before_activity_id

# Areas that should not overlap (ekki_deila_svaedi)
ekki_deila_svaedi = {
    'A-sal': ['1/3 A-sal-1', '1/3 A-sal-2', '1/3 A-sal-3', '2/3 A-sal'],
    '2/3 A-sal': ['1/3 A-sal-1', '1/3 A-sal-2']
}

# --- Gurobi Model and Variables ---
model = gp.Model()
x = model.addVars(EDA, ub=UB)
z = model.addVars(EDA, vtype="B")
M = 24*60
ExE = {(EX[i], EX[j]) for i in range(len(EX)) for j in range(len(EX)) if i != j}
y = model.addVars(ExE, vtype="B")
q = model.addVars(E, range(len(D)))
c = model.addVars(EDA, vtype="B")

# --- Constraints ---

# if the exercise ex is on day d in area a then it should start after LB
model.addConstrs(z[ex, d, a]*LB[(ex, d, a)] <= x[ex, d, a] for (ex, d, a) in EDA)
# if not scheduled, force time to 0
model.addConstrs(x[ex, d, a] <= UB[(ex, d, a)]*z[ex, d, a] for (ex, d, a) in EDA)
# each exercise performed somewhere just once
model.addConstrs(gp.quicksum(z[ex, d, a] for d in D for a in A if (ex, d, a) in EDA) == 1 for ex in EX)
# only once per day or not at all
model.addConstrs(gp.quicksum(z[ex, d, a] for ex in EXsubset[e] for a in A if (ex, d, a) in EDA) <= 1 for d in D for e in E)
# no overlap in exercises if at same location
model.addConstrs(
    x[e1, d, a] + DX[e1] <= x[e2, d, a] + M*(1-z[e1, d, a]) + M*(1-z[e2, d, a]) + M*y[e1, e2]
    for (e1, e2) in ExE for d in D for a in A if (e1, d, a) in EDA and (e2, d, a) in EDA
)
model.addConstrs(
    x[e2, d, a] + DX[e2] <= x[e1, d, a] + M*(1-z[e1, d, a]) + M*(1-z[e2, d, a]) + M*(1-y[e1, e2])
    for (e1, e2) in ExE for d in D for a in A if (e1, d, a) in EDA and (e2, d, a) in EDA
)
# Overlapping area should not be at the same time (not just day for A-sal)
model.addConstrs(
    x[e1, d, a1] + DX[e1] <= x[e2, d, a2] + M*(1-z[e1, d, a1]) + M*(1-z[e2, d, a2]) + M*y[e1, e2]
    for (e1, e2) in ExE for d in D for a1 in ekki_deila_svaedi.keys() for a2 in ekki_deila_svaedi[a1]
    if (e1, d, a1) in EDA and (e2, d, a2) in EDA
)
model.addConstrs(
    x[e2, d, a2] + DX[e2] <= x[e1, d, a1] + M*(1-z[e1, d, a1]) + M*(1-z[e2, d, a2]) + M*(1-y[e1, e2])
    for (e1, e2) in ExE for d in D for a1 in ekki_deila_svaedi.keys() for a2 in ekki_deila_svaedi[a1]
    if (e1, d, a1) in EDA and (e2, d, a2) in EDA
)

# ---- FIXED: Árekstur (conflict) constraints ----
for e1 in CX.keys():
    for ex1 in EXsubset.get(e1, []):
        for e2_name in CX[e1]:
            for ex2 in EXsubset.get(e2_name, []):
                if ex1 == ex2: continue
                for d in D:
                    x1_inds = [(ex1, d, a) for a in A if (ex1, d, a) in EDA]
                    x2_inds = [(ex2, d, a) for a in A if (ex2, d, a) in EDA]
                    if not x1_inds or not x2_inds: continue
                    model.addConstr(
                        gp.quicksum(x[idx] for idx in x1_inds) + DX[ex1] <=
                        gp.quicksum(x[idx] for idx in x2_inds)
                        + M*(1-gp.quicksum(z[idx] for idx in x1_inds))
                        + M*(1-gp.quicksum(z[idx] for idx in x2_inds))
                        + M*y[ex1, ex2]
                    )
                    model.addConstr(
                        gp.quicksum(x[idx] for idx in x2_inds) + DX[ex2] <=
                        gp.quicksum(x[idx] for idx in x1_inds)
                        + M*(1-gp.quicksum(z[idx] for idx in x1_inds))
                        + M*(1-gp.quicksum(z[idx] for idx in x2_inds))
                        + M*(1-y[ex1, ex2])
                    )

# Only allowed days/areas per activity
for (e, a) in [(k[0], k[1]) for k in class_schedule.keys() for k2 in e_a.get(k, [])]:
    if (e, a) in class_schedule.keys():
        allowed_days = set(class_schedule[e].keys())
        model.addConstr(
            gp.quicksum(z[ex, d, a] for d in D for ex in EXsubset[e] if (ex, d, a) in EDA and d not in allowed_days) == 0
        )
# Precedence constraints
model.addConstrs(
    gp.quicksum(x[ex, d, a] + DX[ex]*z[ex, d, a] for ex in EXsubset[e1] for a in A if (ex, d, a) in EDA) <=
    gp.quicksum(x[ex, d, a] for ex in EXsubset[e2] for a in A if (ex, d, a) in EDA)
    + M*(1-gp.quicksum(z[ex, d, a] for ex in EXsubset[e1] for a in A if (ex, d, a) in EDA))
    + M*(1-gp.quicksum(z[ex, d, a] for ex in EXsubset[e2] for a in A if (ex, d, a) in EDA))
    for d in D for e1 in undan_eftir.keys() for e2 in [undan_eftir[e1]]
)
model.addConstrs(
    gp.quicksum(x[ex, d, a] + DX[ex]*z[ex, d, a] for ex in EXsubset[e1] for a in A if (ex, d, a) in EDA) >=
    gp.quicksum(x[ex, d, a] for ex in EXsubset[e2] for a in A if (ex, d, a) in EDA)
    - M*(1-gp.quicksum(z[ex, d, a] for ex in EXsubset[e1] for a in A if (ex, d, a) in EDA))
    - M*(1-gp.quicksum(z[ex, d, a] for ex in EXsubset[e2] for a in A if (ex, d, a) in EDA))
    for d in D for e1 in undan_eftir.keys() for e2 in [undan_eftir[e1]]
)
# Objective: minimize sum of q + bias for early/late/area usage
bias = {a: 1.0 for a in A}
bias['1/3 A-sal-1'] = 1.02
bias['1/3 A-sal-2'] = 1.01
model.setObjective(
    100*gp.quicksum(q[e, i] for e in E for i in range(len(D))) +
    (1/len(EX))*gp.quicksum(bias[a]*x[ex, d, a] for (ex, d, a) in EDA),
    GRB.MINIMIZE
)
model.optimize()

# Output results
if model.status == GRB.OPTIMAL:
    print("\n--- OPTIMAL SCHEDULE ---")
    for (ex, d, a) in EDA:
        if z[ex, d, a].X > 0.5:
            print(f"Exercise {ex} scheduled on {d} in area {a} at time {x[ex, d, a].X:.1f}")
else:
    print("No optimal solution found.")
