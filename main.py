import os
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from sqlalchemy import create_all, create_engine
from sqlalchemy.orm import Session, sessionmaker
from pydantic import BaseModel
from typing import List, Optional
import datetime
import uuid

# Local imports
from models import Base, Outing, AudioTranscript, HypeManFeedback

# App setup
app = FastAPI(title="touchGrass - Audio Driven Outing Tracker")

# Database setup (using SQLite)
SQLALCHEMY_DATABASE_URL = "sqlite:///./touchgrass.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Modules ---

class EventAggregator:
    """To pull and collate local offline events (stub)."""
    async def get_local_events(self, location: str):
        # Implementation to fetch real events would go here
        return [
            {"name": "Community Yoga in the Park", "time": "10:00 AM"},
            {"name": "Farmers Market", "time": "8:00 AM"},
            {"name": "Local Music Festival", "time": "2:00 PM"}
        ]

class HypeManModule:
    """LLM 'Hype Man' Module to process transcript with a system prompt."""
    def __init__(self, api_key: Optional[str] = None):
        self.system_prompt = (
            "You are the ultimate 'Hype Man'. Your goal is to provide immediate, "
            "customized positive reinforcement to the user after they share an outing update. "
            "Keep it energetic, fun, and encouraging. Focus on the benefits of being outdoors "
            "and 'touching grass'."
        )
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")

    async def get_positive_reinforcement(self, transcript: str):
        # Implementation to call LLM (OpenAI/Gemini) goes here.
        # Returning a mock response for now.
        return f"Yo! That sounds absolutely legendary! Getting out there and doing '{transcript}' is exactly what we need! Keep it up, you're crushing it! 🌿✨"

# Initialize modules
event_aggregator = EventAggregator()
hype_man = HypeManModule()

# --- API Endpoints ---

@app.get("/")
async def root():
    return {"message": "Welcome to touchGrass! Go outside and report back."}

@app.get("/events")
async def get_events(location: str = "local"):
    events = await event_aggregator.get_local_events(location)
    return {"location": location, "events": events}

@app.post("/audio/intake")
async def process_audio(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Receive and process short audio voice notes."""
    try:
        # 1. Save audio file
        file_extension = file.filename.split(".")[-1]
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        upload_path = f"uploads/{unique_filename}"
        os.makedirs("uploads", exist_ok=True)
        
        with open(upload_path, "wb") as buffer:
            buffer.write(await file.read())
        
        # 2. Transcribe Audio (Mocking for now)
        mock_transcript = "I just went for a 20 minute walk in the botanical gardens."
        
        # 3. Save to database
        # Create a generic outing for now or link to existing one
        new_outing = Outing(title="New Outing", location="Park")
        db.add(new_outing)
        db.commit()
        db.refresh(new_outing)
        
        db_transcript = AudioTranscript(
            outing_id=new_outing.id,
            audio_path=upload_path,
            transcript=mock_transcript
        )
        db.add(db_transcript)
        db.commit()
        db.refresh(db_transcript)
        
        # 4. Get Hype Man Feedback
        feedback_text = await hype_man.get_positive_reinforcement(mock_transcript)
        
        db_feedback = HypeManFeedback(
            transcript_id=db_transcript.id,
            feedback_text=feedback_text
        )
        db.add(db_feedback)
        db.commit()
        db.refresh(db_feedback)
        
        return {
            "status": "success",
            "transcript": mock_transcript,
            "hype_man_says": feedback_text
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
