# app.py

import streamlit as st
import pandas as pd
from streamlit_calendar import calendar
import datetime

st.set_page_config(page_title="Sports Timetable", layout="wide")

# ---- 1. Fetch timetable data from Google Sheets ----
SHEET_URL = "https://docs.google.com/spreadsheets/d/1B91Ez1iHNW7f0AVKJwURqHhq-vQF3b4F2e-1HcDO2wM/export?format=csv&gid=0"

@st.cache_data
def get_data(url):
    df = pd.read_csv(url)
    # Normalize column names
    df.columns = [col.strip() for col in df.columns]
    return df

df = get_data(SHEET_URL)

if df.empty or not set(['Æfing', 'Salur/svæði']).issubset(df.columns):
    st.error("The Google Sheet does not contain the expected columns ('Æfing', 'Salur/svæði', ...). Please check your data.")
    st.stop()

# ---- 2. Clean and prep data for UI ----
# For demo, create 'Dagur', 'Byrjun', 'Endir' columns if missing
if 'Dagur' not in df.columns:
    import numpy as np
    days = ['mán', 'þri', 'mið', 'fim', 'fös', 'lau', 'sun']
    df['Dagur'] = np.random.choice(days, size=len(df))
    df['Byrjun'] = np.random.choice(['08:00', '10:00', '12:00', '16:00', '18:00'], size=len(df))
    df['Endir'] = np.random.choice(['09:30', '11:30', '13:30', '17:30', '19:30'], size=len(df))

# ---- 3. Sidebar filters ----
st.sidebar.header("Filters")
room_options = sorted({s for sv in df['Salur/svæði'] for s in str(sv).split('|')})
room_filter = st.sidebar.multiselect("Select area(s)", room_options, default=room_options)

exercise_options = sorted(df['Æfing'].unique())
exercise_filter = st.sidebar.multiselect("Select exercise(s)", exercise_options, default=exercise_options)

# ---- 4. Apply filters ----
df_filtered = df[
    df['Æfing'].isin(exercise_filter) &
    df['Salur/svæði'].apply(lambda sv: any(r in str(sv).split('|') for r in room_filter))
].copy()

# ---- 5. Editable Table ----
st.subheader("📋 Timetable Table (Editable)")
edited_df = st.data_editor(
    df_filtered.reset_index(drop=True),
    use_container_width=True,
    num_rows="dynamic",
    key="editable_table"
)

# ---- 6. Optimization button ----
if st.sidebar.button("Run Optimization"):
    st.info("Running optimization on the edited table...")
    # Here is where you should call your optimization logic with 'edited_df'
    # Example: result_df = run_gurobi_optimization(edited_df)
    st.success("Optimization complete! (Demo only)")

# ---- 7. Convert table to calendar events ----
def timetable_to_events(df):
    day_map = {"mán": 0, "þri": 1, "mið": 2, "fim": 3, "fös": 4, "lau": 5, "sun": 6}
    base_date = datetime.date.today() - datetime.timedelta(days=datetime.date.today().weekday())  # Monday

    events = []
    for _, row in df.iterrows():
        day_idx = day_map.get(row['Dagur'], 0)
        try:
            start_hour, start_min = map(int, str(row['Byrjun']).split(':'))
            end_hour, end_min = map(int, str(row['Endir']).split(':'))
        except Exception:
            continue
        date = base_date + datetime.timedelta(days=day_idx)
        start_dt = datetime.datetime.combine(date, datetime.time(start_hour, start_min))
        end_dt = datetime.datetime.combine(date, datetime.time(end_hour, end_min))
        area = str(row['Salur/svæði']).split('|')[0]
        events.append({
            "title": f"{row['Æfing']} ({area})",
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
            "backgroundColor": "#1976D2"
        })
    return events

events = timetable_to_events(edited_df)

# ---- 8. Calendar UI ----
st.subheader("📅 Weekly Timetable")
calendar_options = {
    "initialView": "timeGridWeek",
    "slotMinTime": "08:00:00",
    "slotMaxTime": "23:00:00",
    "allDaySlot": False,
    "locale": "is",
    "firstDay": 1,
    "editable": False,
    "eventDurationEditable": False,
    "eventStartEditable": False,
    "eventResizableFromStart": False,
    "height": "auto",
}
calendar(
    events=events,
    options=calendar_options,
    key="sports-calendar"
)

st.markdown("""
---
*You can edit the table above. When you click "Run Optimization", the edited data will be used as input for the solver!*
""")

