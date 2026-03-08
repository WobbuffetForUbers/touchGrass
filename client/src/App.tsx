import { useState, useEffect, useRef } from 'react'
import { Mic, Flame, CheckCircle, PlusCircle, Check, User as UserIcon, X, Save, Map as MapIcon, List as ListIcon, ArrowUpDown } from 'lucide-react'
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import L from 'leaflet'
import './App.css'

import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerIconRetina from 'leaflet/dist/images/marker-icon-2x.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'

const DefaultIcon = L.icon({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIconRetina,
  shadowUrl: markerShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41]
})
L.Marker.prototype.options.icon = DefaultIcon

interface Event {
  external_id: string
  name: string
  time: string
  type: string
  location: string
  distance?: number
}

interface Preferences {
  goal: number
  interests: string[]
}

function RecenterMap({ coords, zoom = 14 }: { coords: { lat: number, lon: number }, zoom?: number }) {
  const map = useMap()
  useEffect(() => {
    map.setView([coords.lat, coords.lon], zoom)
  }, [coords, zoom, map])
  return null
}

function App() {
  const [view, setView] = useState<'home' | 'profile' | 'map'>('home')
  const [events, setEvents] = useState<Event[]>([])
  const [filter, setFilter] = useState<string>('All')
  const [sortBy, setSortBy] = useState<'distance' | 'name'>('distance')
  const [feedback, setFeedback] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [coords, setCoords] = useState<{ lat: number, lon: number } | null>(null)
  const [mapFocus, setMapFocus] = useState<{ lat: number, lon: number } | null>(null)
  const [streak, setStreak] = useState<number>(0)
  const [rsvpedEvents, setRsvpedEvents] = useState<Set<string>>(new Set())
  const [preferences, setPreferences] = useState<Preferences>({ goal: 3, interests: [] })

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])

  useEffect(() => {
    fetch('/api/user/profile')
      .then(res => res.json())
      .then(data => { 
        setStreak(data.streak_count); 
        setPreferences(data.preferences || { goal: 3, interests: [] }) 
      })
      .catch(err => console.error("Error fetching profile:", err))

    if ("geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition(
        (pos) => setCoords({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
        () => setCoords({ lat: 40.7812, lon: -73.9665 })
      )
    }
  }, [])

  useEffect(() => {
    if (coords) {
      fetch(`/api/events?lat=${coords.lat}&lon=${coords.lon}`)
        .then(res => res.json())
        .then(data => setEvents(data.events))
        .catch(err => console.error("Error fetching events:", err))
    }
  }, [coords])

  const filteredEvents = events
    .filter(e => filter === 'All' || e.type.toLowerCase().includes(filter.toLowerCase()))
    .sort((a, b) => {
      if (sortBy === 'distance') return (a.distance || 0) - (b.distance || 0)
      return a.name.localeCompare(b.name)
    })

  const focusOnEvent = (event: Event) => {
    const [lat, lon] = event.location.split(',').map(Number)
    setMapFocus({ lat, lon })
    setView('map')
  }

  const startRecording = async () => {
    setFeedback(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mediaRecorder = new MediaRecorder(stream)
      mediaRecorderRef.current = mediaRecorder
      audioChunksRef.current = []
      mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) audioChunksRef.current.push(e.data) }
      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' })
        await uploadAudio(audioBlob)
        stream.getTracks().forEach(t => t.stop())
      }
      mediaRecorder.start()
      setIsRecording(true)
    } catch (err) {
      console.error("Microphone error:", err)
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop()
      setIsRecording(false)
    }
  }

  const uploadAudio = async (blob: Blob) => {
    setLoading(true)
    const formData = new FormData()
    formData.append('file', blob, 'recording.webm')
    try {
      const res = await fetch('/api/audio/intake', { method: 'POST', body: formData })
      const data = await res.json()
      setFeedback(data.hype_man_says)
      setStreak(data.streak_count)
    } catch (err) {
      console.error("Processing error:", err)
    } finally {
      setLoading(false)
    }
  }

  const handleRSVP = async (event: Event) => {
    try {
      const res = await fetch('/api/events/rsvp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ event_external_id: event.external_id, name: event.name, type: event.type })
      })
      if (res.ok) { 
        setRsvpedEvents(prev => new Set(prev).add(event.external_id))
        setFeedback(`Going to ${event.name}!`) 
      }
    } catch (err) {
      console.error("RSVP error:", err)
    }
  }

  if (view === 'profile') {
    return (
      <div className="app-container">
        <header className="header">
          <h1>Profile</h1>
          <button onClick={() => setView('home')} className="icon-button"><X /></button>
        </header>
        <main className="content profile-content">
          <div className="profile-card">
            <div className="stat-row">
              <Flame color="#ff4500" />
              <span>{streak} Day Streak</span>
            </div>
          </div>
          <div className="settings-section">
            <label>Outing Goal (per week)</label>
            <input 
              type="number" 
              value={preferences.goal} 
              onChange={(e) => setPreferences({...preferences, goal: parseInt(e.target.value)})} 
            />
            <label>Interests</label>
            <input 
              type="text" 
              value={preferences.interests.join(", ")} 
              onChange={(e) => setPreferences({...preferences, interests: e.target.value.split(",").map(i => i.trim())})} 
            />
          </div>
          <button className="save-button" onClick={() => {
            fetch('/api/user/profile', { 
              method: 'PUT', 
              headers: { 'Content-Type': 'application/json' }, 
              body: JSON.stringify({ preferences }) 
            })
            .then(() => setView('home'))
          }}><Save size={20} /> Save</button>
        </main>
      </div>
    )
  }

  return (
    <div className="app-container">
      <header className="header">
        <h1>touchGrass</h1>
        <div className="header-actions">
          <div className="streak-badge"><Flame size={20} color="#ff4500" /><span>{streak}</span></div>
          <button onClick={() => setView('profile')} className="icon-button"><UserIcon /></button>
        </div>
      </header>

      <main className="content">
        <div className="view-toggle">
          <button onClick={() => setView('home')} className={view === 'home' ? 'active' : ''}><ListIcon size={18} /> List</button>
          <button onClick={() => setView('map')} className={view === 'map' ? 'active' : ''}><MapIcon size={18} /> Map</button>
        </div>

        {view === 'map' && coords && (
          <div className="map-view animate-fade-in">
            <MapContainer center={[mapFocus?.lat || coords.lat, mapFocus?.lon || coords.lon]} zoom={mapFocus ? 16 : 14} style={{ height: '100%', width: '100%', borderRadius: '1.5rem' }}>
              <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
              <RecenterMap coords={mapFocus || coords} zoom={mapFocus ? 16 : 14} />
              <Marker position={[coords.lat, coords.lon]} icon={DefaultIcon}><Popup>You!</Popup></Marker>
              {events.map((e, idx) => {
                const [lt, ln] = e.location.split(',').map(Number)
                return <Marker key={idx} position={[lt, ln]}><Popup><strong>{e.name}</strong><br/>{e.type}</Popup></Marker>
              })}
            </MapContainer>
          </div>
        )}

        {view === 'home' && (
          <section className="events-section">
            <div className="filter-controls">
              <div className="pills">
                {['All', 'Park', 'Event', 'Music', 'Sports'].map(cat => (
                  <button key={cat} onClick={() => setFilter(cat)} className={filter === cat ? 'active' : ''}>{cat}</button>
                ))}
              </div>
              <button className="sort-btn" onClick={() => setSortBy(sortBy === 'distance' ? 'name' : 'distance')}>
                <ArrowUpDown size={14} /> {sortBy === 'distance' ? 'Closest' : 'A-Z'}
              </button>
            </div>

            <div className="event-list">
              {filteredEvents.map((event, idx) => (
                <div key={idx} className="event-card">
                  <div className="event-info" onClick={() => focusOnEvent(event)}>
                    <strong>{event.name}</strong>
                    <span>{event.distance}km • {event.type}</span>
                  </div>
                  <button className={`rsvp-button ${rsvpedEvents.has(event.external_id) ? 'active' : ''}`} onClick={() => handleRSVP(event)}>
                    {rsvpedEvents.has(event.external_id) ? <Check size={18} /> : <PlusCircle size={18} />}
                  </button>
                </div>
              ))}
            </div>
          </section>
        )}

        {feedback && (
          <section className="feedback-section animate-fade-in">
            <div className="feedback-card"><CheckCircle size={24} color="#4ade80" /><p>{feedback}</p></div>
          </section>
        )}
      </main>

      <footer className="footer">
        <button 
          className={`record-button ${isRecording ? 'recording' : ''}`} 
          onClick={isRecording ? stopRecording : startRecording} 
          disabled={loading}
        >
          {loading ? <div className="spinner"></div> : <Mic size={32} color="white" />}
        </button>
      </footer>
    </div>
  )
}

export default App
