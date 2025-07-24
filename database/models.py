from sqlalchemy import Column, String, Integer, Float, Boolean, Date, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Club(Base):
    __tablename__ = 'clubs'
    club_id = Column(String, primary_key=True)
    name = Column(String)

class Area(Base):
    __tablename__ = 'areas'
    area_id = Column(String, primary_key=True)
    name = Column(String)

class Activity(Base):
    """
    Represents one row from your data file (e.g., "4 fl kk fótbolti").
    """
    __tablename__ = 'activities'
    activity_id = Column(String, primary_key=True)     # "Æfing"
    club_id = Column(String, ForeignKey('clubs.club_id'))
    groups_count = Column(Integer)                     # Æfingarhópar
    prerequisite_activity_id = Column(String)          # fyrir/undan (optional)
    weekend_count = Column(Integer)                    # Fjöldi helgaræfinga
    week_count = Column(Integer)                       # Fjöldi vikuæfinga
    length_str = Column(String)                        # Lengd (comma string)
    length_weekend_str = Column(String)                # LengdHelgar (comma string)
    conflict_str = Column(String)                      # Árekstur (pipe string)
    same_time_str = Column(String)                     # Sama tíma (pipe string)
    period_start = Column(Date)
    period_end = Column(Date)
    participant_count = Column(Integer)                # Fjöldi iðkennda
    sessions = relationship("Session", back_populates="activity")

class Session(Base):
    """
    Each possible assignment of an activity to an area on a specific day.
    """
    __tablename__ = 'sessions'
    session_id = Column(Integer, primary_key=True, autoincrement=True)
    activity_id = Column(String, ForeignKey('activities.activity_id'))
    day_of_week = Column(String)         # 'sun', 'mán', etc.
    area_id = Column(String, ForeignKey('areas.area_id'))
    min_start = Column(Integer)          # Minutes from midnight
    max_end = Column(Integer)            # Minutes from midnight
    activity = relationship("Activity", back_populates="sessions")
    area = relationship("Area")

class Conflict(Base):
    """
    Activity-level conflicts (from Árekstur).
    """
    __tablename__ = 'conflicts'
    id = Column(Integer, primary_key=True, autoincrement=True)
    activity_id = Column(String, ForeignKey('activities.activity_id'))
    conflict_activity_id = Column(String)  # not FK, for flexibility

class Prerequisite(Base):
    """
    For fyrir/undan (precedence).
    """
    __tablename__ = 'prerequisites'
    id = Column(Integer, primary_key=True, autoincrement=True)
    activity_id = Column(String, ForeignKey('activities.activity_id'))
    must_be_before_activity_id = Column(String)  # not FK, for flexibility

