from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    preferences = Column(JSON, default={})
    streak_count = Column(Integer, default=0)
    last_log_date = Column(DateTime)
    
    logs = relationship("Log", back_populates="user")
    rsvps = relationship("RSVP", back_populates="user")
    facts = relationship("UserFact", back_populates="user")

class UserFact(Base):
    """Stores key facts about the user extracted by the AI."""
    __tablename__ = "user_facts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    fact = Column(String)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="facts")

class Event(Base):
    """Stores local green spaces or community events pulled from APIs."""
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String, unique=True, index=True) # e.g. OSM ID or Ticketmaster ID
    name = Column(String)
    type = Column(String) # Park, Garden, Concert, etc.
    location = Column(String) # Lat, Lon or Address
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    
    rsvps = relationship("RSVP", back_populates="event")

class RSVP(Base):
    """Tracks user intent to attend an event."""
    __tablename__ = "rsvps"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    event_id = Column(Integer, ForeignKey("events.id"))
    status = Column(String, default="going") # going, checked_in
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    user = relationship("User", back_populates="rsvps")
    event = relationship("Event", back_populates="rsvps")

class Log(Base):
    """Consolidated record of a user outing and AI feedback."""
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    audio_path = Column(String)
    transcript = Column(Text) # Extracted from Gemini's processing
    llm_response = Column(Text)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    
    user = relationship("User", back_populates="logs")
