import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from database.models import Base, Club, Area, Activity, Session, Conflict, Prerequisite

url = 'https://docs.google.com/spreadsheets/d/1CGmM0ZN0Mi5mU0RoL4JeiJQjyUBJhI8Gf3u-oPvGn6E/export?format=csv&id=1CGmM0ZN0Mi5mU0RoL4JeiJQjyUBJhI8Gf3u-oPvGn6E&gid=0'
df = pd.read_csv(url)

# --- Split 'Salur/svæði' into set of area names ---
df['Salur/svæði'] = df['Salur/svæði'].str.split('|').apply(lambda x: set(item.strip() for item in x) if isinstance(x, list) else set())

# --- Set up SQLAlchemy session ---
engine = create_engine('sqlite:///sports_schedule.db')
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

# --- Add Club (single club for now) ---
club = Club(club_id='1', name='MyClub')
db.merge(club)
db.commit()

# --- Areas: collect all unique area names ---
all_areas = set()
for areas in df['Salur/svæði']:
    all_areas.update(areas)
for area_name in all_areas:
    area = Area(area_id=area_name, name=area_name)
    db.merge(area)
db.commit()

# --- Activities and Sessions ---
DAYS = ['sun', 'mán', 'þri', 'mið', 'fim', 'fös', 'lau']

def parse_date(val):
    if pd.isna(val):
        return None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(val), fmt).date()
        except Exception:
            continue
    return None

for idx, row in df.iterrows():
    activity_id = row['Æfing']
    activity = Activity(
        activity_id = activity_id,
        club_id = club.club_id,
        groups_count = int(row['Æfingarhópar']) if not pd.isna(row['Æfingarhópar']) else None,
        prerequisite_activity_id = row['fyrir/undan'] if not pd.isna(row['fyrir/undan']) else None,
        weekend_count = int(row['Fjöldi helgaræfinga']) if not pd.isna(row['Fjöldi helgaræfinga']) else None,
        week_count = int(row['Fjöldi vikuæfinga']) if not pd.isna(row['Fjöldi vikuæfinga']) else None,
        length_str = ','.join(str(x).strip() for x in str(row['Lengd']).split(',')) if not pd.isna(row['Lengd']) else None,
        length_weekend_str = ','.join(str(x).strip() for x in str(row['LengdHelgar']).split(',')) if not pd.isna(row['LengdHelgar']) else None,
        conflict_str = str(row['Árekstur']) if not pd.isna(row['Árekstur']) else None,
        same_time_str = str(row['Sama tíma']) if 'Sama tíma' in row and not pd.isna(row['Sama tíma']) else None,
        period_start = parse_date(row['Tímabil byrjar']) if 'Tímabil byrjar' in row else None,
        period_end = parse_date(row['tímabil endar']) if 'tímabil endar' in row else None,
        participant_count = int(row['Fjöldi iðkennda']) if not pd.isna(row['Fjöldi iðkennda']) else None
    )
    db.merge(activity)

    # Sessions: for each area and day where there is a time
    for area_id in row['Salur/svæði']:
        for d in DAYS:
            time_range = row[d] if d in row and not pd.isna(row[d]) else None
            if time_range:
                try:
                    start, end = [t.strip() for t in time_range.split('-')]
                    h1, m1 = map(int, start.split(':'))
                    h2, m2 = map(int, end.split(':'))
                    min_start = h1*60 + m1
                    max_end = h2*60 + m2
                except Exception:
                    min_start = None
                    max_end = None
                sess = Session(
                    activity_id=activity_id,
                    day_of_week=d,
                    area_id=area_id,
                    min_start=min_start,
                    max_end=max_end
                )
                db.add(sess)
db.commit()

# --- Conflicts (Árekstur) ---
for idx, row in df.iterrows():
    if not pd.isna(row['Árekstur']):
        activity_id = row['Æfing']
        for c in row['Árekstur'].split('|'):
            c = c.strip()
            if c:
                db.add(Conflict(activity_id=activity_id, conflict_activity_id=c))
db.commit()

# --- Prerequisites (fyrir/undan) ---
for idx, row in df.iterrows():
    if not pd.isna(row['fyrir/undan']):
        db.add(Prerequisite(activity_id=row['Æfing'], must_be_before_activity_id=row['fyrir/undan']))
db.commit()

print("Import complete!")

