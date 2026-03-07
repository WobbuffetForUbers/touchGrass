from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import datetime

Base = declarative_base()

class Outing(Base):
    __tablename__ = "outings"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    description = Column(Text)
    location = Column(String)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    
    transcripts = relationship("AudioTranscript", back_populates="outing")

class AudioTranscript(Base):
    __tablename__ = "audio_transcripts"

    id = Column(Integer, primary_key=True, index=True)
    outing_id = Column(Integer, ForeignKey("outings.id"))
    audio_path = Column(String)
    transcript = Column(Text)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    
    outing = relationship("Outing", back_populates="transcripts")
    feedback = relationship("HypeManFeedback", back_populates="transcript", uselist=False)

class HypeManFeedback(Base):
    __tablename__ = "hypeman_feedback"

    id = Column(Integer, primary_key=True, index=True)
    transcript_id = Column(Integer, ForeignKey("audio_transcripts.id"))
    feedback_text = Column(Text)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    
    transcript = relationship("AudioTranscript", back_populates="feedback")
