touchGrass: System Architecture
1. Project Overview
touchGrass is an Online-to-Offline (O2O) application designed to facilitate physical-world engagement. It uses an active LLM "Hype Man" persona to provide immediate, customized positive reinforcement, reducing the friction of logging offline activities.

2. Tech Stack
Backend Framework: FastAPI (Python) for asynchronous endpoints and rapid LLM integration.

Database: SQL (PostgreSQL or SQLite for development) to store user logs, event data, and LLM context.

ORM: SQLAlchemy for database management.

AI Integration: Direct API calls to Gemini (or preferred LLM) using a strict system prompt.

Audio Processing: Whisper API (or similar lightweight transcription model) for voice-to-text intake.

3. Core System Components
Client Interface: Minimal UI focused on local event display and a central audio-record button.

API Gateway (FastAPI): Routes client requests, handles authentication, and manages data payloads.

Event Aggregator Service: Pulls local event data (APIs, webhooks, or manual entry) and serves it to the client.

Transcription Service: Converts user audio logs into text strings.

LLM Engine: Ingests transcriptions and historical user context, applies the "Hype Man" system prompt, and generates the feedback string.

Context Database (SQL): Stores user history to allow the LLM to reference past improvements and maintain a continuous behavioral loop.

4. Core Workflow: The "Hype Man" Loop
Trigger: User attends an offline event (e.g., local dance social, community jam).

Input: User presses the audio button and records a brief summary of the experience.

Processing: * Client sends audio payload to /api/v1/log-audio.

FastAPI routes audio to the Transcription Service.

Transcribed text and User ID are sent to the LLM Engine.

Reward: LLM generates a 1-3 sentence tailored response validating the effort and ends with a follow-up question.

Storage & Delivery: FastAPI logs the interaction in the SQL database and returns the text/audio response to the client UI.

5. Data Model (Draft)
Users: user_id, preferences, streak_count

Events: event_id, location, type, date

Logs: log_id, user_id, transcript, llm_response, timestamp