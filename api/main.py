import os
import uuid
import datetime
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from dotenv import load_dotenv
import math
import google.generativeai as genai
import requests

# Load environment variables
load_dotenv()

# Local imports
from models import Base, User, Event, Log, RSVP

# App setup
app = FastAPI(title="touchGrass - AI Hype Man")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup (using SQLite)
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./touchgrass.db")
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

# --- Pydantic Schemas ---
class RSVPRequest(BaseModel):
    event_external_id: str
    name: str
    type: str

class ProfileUpdate(BaseModel):
    preferences: dict

# --- Modules ---

class EventAggregator:
    """To pull and collate local offline events (OSM Parks + Ticketmaster Events)."""
    def __init__(self):
        self.tm_api_key = os.getenv("TICKETMASTER_API_KEY")

    async def get_local_events(self, lat: float, lon: float, db: Session):
        # 1. Fetch Parks from OpenStreetMap (OSM)
        parks = await self._fetch_osm_parks(lat, lon, db)
        
        # 2. Fetch Events from Ticketmaster
        tm_events = await self._fetch_tm_events(lat, lon, db)
        
        # Combine and calculate distances
        all_events = tm_events + parks
        for event in all_events:
            e_lat, e_lon = map(float, event["location"].split(","))
            event["distance"] = round(self._calc_dist(lat, lon, e_lat, e_lon), 2)
        
        # Sort by distance by default
        all_events.sort(key=lambda x: x["distance"])
        return all_events

    def _calc_dist(self, lat1, lon1, lat2, lon2):
        return math.sqrt((lat1 - lat2)**2 + (lon1 - lon2)**2) * 111

    async def _fetch_osm_parks(self, lat: float, lon: float, db: Session):
        overpass_url = "https://overpass-api.de/api/interpreter"
        overpass_query = f"""
        [out:json];
        (
          node["leisure"="park"](around:5000,{lat},{lon});
          way["leisure"="park"](around:5000,{lat},{lon});
          node["leisure"="garden"](around:5000,{lat},{lon});
          way["leisure"="garden"](around:5000,{lat},{lon});
        );
        out center;
        """
        try:
            response = requests.post(overpass_url, data={'data': overpass_query}, timeout=10)
            data = response.json()
            parks_out = []
            for element in data.get('elements', []):
                external_id = str(element.get('id'))
                name = element.get('tags', {}).get('name', 'Local Green Space')
                type_ = "Park"
                center = element.get('center', {}) or {"lat": element.get('lat'), "lon": element.get('lon')}
                coords = f"{center.get('lat')},{center.get('lon')}"
                self._save_to_db(external_id, name, type_, coords, db)
                parks_out.append({"external_id": external_id, "name": name, "time": "Open Today", "type": "Park", "location": coords})
            return parks_out
        except: return []

    async def _fetch_tm_events(self, lat: float, lon: float, db: Session):
        if not self.tm_api_key: return []
        tm_url = f"https://app.ticketmaster.com/discovery/v2/events.json?apikey={self.tm_api_key}&latlong={lat},{lon}&radius=10&unit=km"
        try:
            response = requests.get(tm_url, timeout=10)
            data = response.json()
            events_out = []
            for event in data.get('_embedded', {}).get('events', []):
                external_id = event.get('id')
                name = event.get('name')
                type_ = event.get('classifications', [{}])[0].get('segment', {}).get('name', 'Event')
                venue = event.get('_embedded', {}).get('venues', [{}])[0]
                coords = f"{venue.get('location', {}).get('latitude')},{venue.get('location', {}).get('longitude')}"
                self._save_to_db(external_id, name, type_, coords, db)
                events_out.append({"external_id": external_id, "name": name, "time": event.get('dates', {}).get('start', {}).get('localTime', 'TBA'), "type": type_, "location": coords})
            return events_out
        except: return []

    def _save_to_db(self, external_id, name, type_, location, db: Session):
        existing = db.query(Event).filter(Event.external_id == external_id).first()
        if not existing:
            new_event = Event(external_id=external_id, name=name, type=type_, location=location)
            db.add(new_event)
            db.commit()

class HypeManModule:
    """LLM 'Hype Man' Module to process audio and generate reinforcement with history and memory."""
    def __init__(self, api_key: Optional[str] = None):
        api_key = api_key or os.getenv("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel("gemini-2.5-flash")
        else:
            self.model = None

        self.system_prompt_base = (
            "You are the ultimate 'Hype Man'. Your goal is to provide immediate, "
            "customized positive reinforcement to the user after they share an outing update. "
            "The user will provide an audio description of their outdoor activity.\n\n"
            "INSTRUCTIONS:\n"
            "1. Summarize their activity and its benefits concisely.\n"
            "2. Provide energetic, fun, and encouraging feedback.\n"
            "3. Reference their progress or consistency using provided history.\n"
            "4. Identify any NEW facts about the user (e.g. hobbies, names, pets, preferences).\n"
            "5. End with a follow-up question.\n\n"
            "RESPONSE FORMAT: You MUST return a JSON object with two keys: 'feedback' (the hype response) and 'new_facts' (a list of string facts discovered in this interaction, or an empty list if none)."
        )

    async def get_positive_reinforcement(self, audio_path: str, history_context: str = "", preferences: dict = {}, memory_facts: List[str] = []):
        if not self.model:
            return {"feedback": "Yo! That sounds legendary!", "new_facts": []}
        
        prompt = self.system_prompt_base
        if preferences:
            prompt += f"\n\n### USER PREFERENCES:\n{preferences}"
        if memory_facts:
            prompt += f"\n\n### LONG-TERM MEMORY (Facts you know about user):\n{memory_facts}"
        if history_context:
            prompt += f"\n\n### RECENT LOG HISTORY:\n{history_context}"

        try:
            with open(audio_path, "rb") as f:
                audio_data = f.read()
            
            response = self.model.generate_content([
                prompt,
                {
                    "mime_type": "audio/webm",
                    "data": audio_data
                }
            ], generation_config={"response_mime_type": "application/json"})
            
            import json
            # Robust JSON cleaning (sometimes LLMs wrap in ```json ... ```)
            raw_text = response.text.strip()
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
            
            return json.loads(raw_text)
        except Exception as e:
            print(f"Gemini API or JSON error: {e}")
            print(f"Raw response was: {response.text if 'response' in locals() else 'None'}")
            return {"feedback": f"Yo! My hype circuits are fried, but I know you crushed it! (Error: {str(e)})", "new_facts": []}

# Initialize modules
event_aggregator = EventAggregator()
hype_man = HypeManModule()

# --- Helpers ---

def get_or_create_default_user(db: Session):
    user = db.query(User).filter(User.username == "default_user").first()
    if not user:
        user = User(username="default_user", streak_count=0)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

def update_streak(user: User, db: Session):
    now = datetime.datetime.utcnow()
    if user.last_log_date:
        delta = now.date() - user.last_log_date.date()
        if delta.days == 1:
            user.streak_count += 1
        elif delta.days > 1:
            user.streak_count = 1
    else:
        user.streak_count = 1
    
    user.last_log_date = now
    db.commit()
    return user.streak_count

# --- API Endpoints ---

@app.get("/")
async def root():
    return {"message": "Welcome to touchGrass! Go outside and report back."}

@app.get("/events")
async def get_events(lat: float = 40.7812, lon: float = -73.9665, db: Session = Depends(get_db)):
    """Fetch real-time parks and gardens nearby based on coordinates."""
    events = await event_aggregator.get_local_events(lat=lat, lon=lon, db=db)
    return {"location": f"{lat},{lon}", "events": events}

@app.post("/events/rsvp")
async def rsvp_to_event(req: RSVPRequest, db: Session = Depends(get_db)):
    user = get_or_create_default_user(db)
    event = db.query(Event).filter(Event.external_id == req.event_external_id).first()
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found in system")
    
    # Check if already RSVP'd
    existing_rsvp = db.query(RSVP).filter(RSVP.user_id == user.id, RSVP.event_id == event.id).first()
    if existing_rsvp:
        return {"status": "already_going", "message": f"You're already heading to {event.name}!"}
    
    new_rsvp = RSVP(user_id=user.id, event_id=event.id, status="going")
    db.add(new_rsvp)
    db.commit()
    
    return {"status": "success", "message": f"Sweet! We've got you down for {event.name}. See you out there!"}

@app.post("/audio/intake")
async def process_audio(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Receive audio, recall memory, generate feedback, and store new facts."""
    try:
        user = get_or_create_default_user(db)
        
        # 1. Save audio file
        file_extension = file.filename.split(".")[-1]
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        upload_path = f"uploads/{unique_filename}"
        os.makedirs("uploads", exist_ok=True)
        
        with open(upload_path, "wb") as buffer:
            buffer.write(await file.read())
        
        # 2. Recall Memory (Long-term Facts)
        facts_db = db.query(UserFact).filter(UserFact.user_id == user.id).all()
        memory_list = [f.fact for f in facts_db]
        
        # 3. Get Recent Context
        recent_logs = db.query(Log).filter(Log.user_id == user.id).order_by(Log.timestamp.desc()).limit(3).all()
        history_str = "\n".join([f"- User said: {l.transcript}\n- You replied: {l.llm_response}" for l in recent_logs])
        preferences = user.preferences or {"goal": 3, "interests": []}

        # 4. Get Hype Man Feedback + New Memories
        result = await hype_man.get_positive_reinforcement(upload_path, history_str, preferences, memory_list)
        feedback_text = result.get("feedback", "Legendary work!")
        new_facts = result.get("new_facts", [])
        
        # 5. Save New Facts to Long-term Memory
        for fact_str in new_facts:
            if fact_str not in memory_list:
                db.add(UserFact(user_id=user.id, fact=fact_str))
        
        # 6. Update Streak
        new_streak = update_streak(user, db)
        
        # 7. Save Log
        new_log = Log(
            user_id=user.id,
            audio_path=upload_path,
            transcript="Audio processed by Hype Man",
            llm_response=feedback_text
        )
        db.add(new_log)
        db.commit()
        
        return {
            "status": "success",
            "hype_man_says": feedback_text,
            "streak_count": new_streak
        }
    except Exception as e:
        print(f"Server error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/user/stats")
async def get_stats(db: Session = Depends(get_db)):
    user = get_or_create_default_user(db)
    return {
        "streak_count": user.streak_count,
        "last_log": user.last_log_date
    }

@app.get("/user/profile")
async def get_profile(db: Session = Depends(get_db)):
    user = get_or_create_default_user(db)
    return {
        "username": user.username,
        "streak_count": user.streak_count,
        "preferences": user.preferences or {"goal": 3, "interests": []},
        "last_log_date": user.last_log_date
    }

@app.put("/user/profile")
async def update_profile(req: ProfileUpdate, db: Session = Depends(get_db)):
    user = get_or_create_default_user(db)
    # Ensure nested objects are handled properly for SQLAlchemy JSON column
    from sqlalchemy.orm.attributes import flag_modified
    user.preferences = req.preferences
    flag_modified(user, "preferences")
    db.commit()
    return {"status": "success", "preferences": user.preferences}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
