# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Voice AI IVR system built over a 2-week ramp-up program. Combines Flask web server, Plivo telephony, and AI voice capabilities (OpenAI Whisper, GPT, ElevenLabs).

## Directory Structure

```
first-project/
├── week1/                    # TELEPHONY (Flask IVR + Plivo)
│   ├── app.py               # Flask web server, API routes
│   ├── ivr.py               # Plivo IVR routes (XML responses)
│   ├── config.py            # Environment variable loading
│   ├── models.py            # SQLAlchemy database models
│   ├── checker.py           # Utility checker
│   ├── main.py              # Entry point
│   ├── test_call.py         # Call testing
│   └── templates/
│       ├── simulator.html   # Web-based IVR simulator
│       └── call.html        # Outbound call trigger UI
│
├── week2/                    # VOICE AI (STT, LLM, TTS, Pipecat)
│   ├── llm.py               # OpenAI integration (chat, streaming, function calling)
│   ├── speech.py            # OpenAI Whisper STT + ElevenLabs TTS
│   ├── voice_bot.py         # Voice assistant (Python 3.9 compatible)
│   ├── pipecat_bot.py       # Real-time Pipecat voice bot (Python 3.11)
│   ├── pipecat_ivr.py       # Phone-to-AI integration via WebSocket (Python 3.11)
│   └── voice_ivr.py         # Alternative WebSocket integration
│
├── api/                      # VERCEL DEPLOYMENT
│   └── index.py             # Serverless entry point (production IVR)
│
├── .env                      # Environment variables (shared)
├── requirements.txt          # Python dependencies
└── vercel.json              # Vercel configuration
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      VOICE AI SYSTEM                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   TELEPHONY (Week 1):                                       │
│   Phone Call ──► Plivo ──► Flask IVR ──► XML Response       │
│                                                             │
│   VOICE AI (Week 2):                                        │
│   Microphone ──► Whisper ──► GPT-4o ──► ElevenLabs ──► Speaker │
│      (VAD)       (STT)       (LLM)        (TTS)             │
│                                                             │
│   INTEGRATION (Week 2 Day 5):                               │
│   Phone ──► Plivo ──► WebSocket ──► Pipecat ──► AI Response │
│                         ↓                                   │
│              Whisper STT → GPT → ElevenLabs TTS             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Commands

```bash
# === WEEK 1: Telephony ===

# Run Flask server (IVR + API)
python3 week1/app.py

# === WEEK 2: Voice AI ===

# Run LLM demo
python3 week2/llm.py

# Run speech demo (Whisper STT + ElevenLabs TTS)
python3 week2/speech.py

# Run voice bot (text mode)
python3 week2/voice_bot.py

# Run Pipecat voice bot (REQUIRES Python 3.11)
python3.11 week2/pipecat_bot.py

# Run Pipecat IVR integration (Phone-to-AI, REQUIRES Python 3.11)
python3.11 week2/pipecat_ivr.py

# === DEPLOYMENT ===

# Deploy to Vercel
vercel --prod
```

## Environment Variables

Required in `.env` (root directory):
```
PLIVO_AUTH_ID=xxx
PLIVO_AUTH_TOKEN=xxx
OPENAI_API_KEY=xxx          # Used for GPT + Whisper STT
ELEVENLABS_API_KEY=xxx      # Used for TTS
SECRET_KEY=xxx              # Optional, for Flask sessions
```

**Note:** Deepgram is NOT required. OpenAI Whisper is used for STT instead.

## Week 1: IVR Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/voice/incoming` | POST | Plivo webhook - incoming call handler |
| `/voice/menu` | POST | Plivo webhook - menu selection handler |
| `/simulator` | GET | Web-based IVR simulator |
| `/` | GET | Health check / info |
| `/health` | GET | System health status |
| `/calls` | GET/POST | Call log CRUD |
| `/call` | GET | Outbound call trigger UI |
| `/make-call` | POST | Initiate outbound call via Plivo |

## Week 2: Pipecat IVR Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Health check |
| `/voice/incoming` | POST | IVR entry with AI option |
| `/voice/menu` | POST | Menu handler (press 3 for AI) |
| `/voice/ai-direct` | POST | Direct AI connection |
| `/ws/audio` | WebSocket | Audio streaming |

## Testing

- **IVR Simulator**: http://localhost:5001/simulator (test without real phone)
- **Call UI**: http://localhost:5001/call (trigger real outbound calls)
- **Voice Bot (text mode)**: `python3 week2/voice_bot.py` → choose mode 2
- **Pipecat Bot (full voice)**: `python3.11 week2/pipecat_bot.py`
- **Phone-to-AI**: Call Plivo number, press 3

## Deployment

### Vercel (Production)
- **Live URL**: https://demo-ivr.vercel.app
- **Entry point**: `api/index.py`
- **Database**: Vercel Postgres (Neon) - auto-configured via `DATABASE_URL`

```bash
vercel --prod    # Deploy to production
vercel           # Deploy to preview
```

### Local Development
```bash
# Week 1: Flask IVR
python3 week1/app.py
ngrok http 5001

# Week 2: Pipecat IVR
python3.11 week2/pipecat_ivr.py
ngrok http 8000
```

## Plivo Configuration

- **Console**: console.plivo.in (Indian account)
- **Phone Number**: +91 80354 53216 (Bangalore)
- **Application**: My-IVR

### Plivo XML Guidelines
1. **Always use absolute URLs** in `action` attributes
2. **Don't use `voice` attribute** - Polly voices may not be available
3. **Avoid `<Hangup/>` tags** unless you explicitly want to end the call
4. **Use POST method** for GetDigits action URLs

## Pipecat Voice Bot (Week 2)

### Requirements
- Python 3.11+ (uses `match` statements)
- PyAudio (for microphone access)
- Pipecat-ai with extras

### Installation
```bash
brew install python@3.11 portaudio
pip3.11 install python-dotenv openai httpx pyaudio "pipecat-ai[openai,elevenlabs,silero]"
```

### Pipeline Architecture
```
Microphone → VAD → Whisper STT → GPT-4o-mini → ElevenLabs TTS → Speaker
```

### Exit Words
Say any of these to end conversation: `goodbye`, `bye`, `exit`, `quit`, `stop`

## Common Issues & Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| Busy tone on call | Invalid XML or unreachable webhook | Check XML syntax, use absolute URLs |
| Call cuts immediately | `voice` attribute not supported | Remove `voice="Polly.Amy"` |
| ElevenLabs 401 error | Deprecated model | Use `eleven_turbo_v2_5` |
| Pipecat SyntaxError | Python version too old | Use `python3.11` |
| VAD not detecting voice | Settings too strict | Lower `confidence` in VADParams |
| Bot responds to itself | Echo from speakers | Use headphones |

## Python Version Notes

| Directory | Python Version | Reason |
|-----------|----------------|--------|
| `week1/*` | 3.9+ | Standard Flask/OpenAI |
| `week2/pipecat_*.py` | **3.11+** | Pipecat uses `match` statements |
| `week2/llm.py`, `week2/speech.py` | 3.9+ | Standard OpenAI |
