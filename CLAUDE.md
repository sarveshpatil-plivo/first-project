# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Voice AI IVR system built over a 2-week ramp-up program. Combines Flask web server, Plivo telephony, and AI voice capabilities (OpenAI Whisper, GPT, ElevenLabs).

## Directory Structure

```
first-project/
├── week1/                    # TELEPHONY (Flask IVR + Plivo) - Local Development
│   ├── app.py               # Flask web server, API routes
│   ├── ivr.py               # Plivo IVR routes (XML responses)
│   ├── config.py            # Environment variable loading
│   ├── models.py            # SQLAlchemy database models
│   ├── checker.py           # Plivo account health checker
│   ├── folder_scanner.py    # CLI folder scanner tool
│   ├── main.py              # Entry point
│   ├── test_call.py         # Call testing
│   └── templates/
│       ├── simulator.html   # Web-based IVR simulator
│       └── call.html        # Outbound call trigger UI
│
├── week2/                    # VOICE AI (STT, LLM, TTS, Pipecat, LiveKit)
│   ├── llm.py               # OpenAI integration (chat, streaming, function calling)
│   ├── speech.py            # OpenAI Whisper STT + ElevenLabs TTS
│   ├── voice_bot.py         # Voice assistant (Python 3.9 compatible)
│   ├── pipecat_bot.py       # Real-time Pipecat voice bot (Python 3.11)
│   ├── pipecat_ivr.py       # Phone-to-AI integration via WebSocket (Python 3.11)
│   ├── voice_ivr.py         # Alternative WebSocket integration
│   ├── livekit_agent.py     # LiveKit AI Receptionist (Python 3.11) - Day 5
│   ├── sip_forward.py       # Plivo-to-LiveKit SIP bridge - Day 5
│   ├── dashboard.py         # Demo dashboard web UI - Day 7
│   ├── Dockerfile           # Railway deployment config - Day 6
│   ├── railway.json         # Railway settings - Day 6
│   └── requirements-livekit.txt  # LiveKit dependencies - Day 6
│
├── api/                      # VERCEL DEPLOYMENT (Production)
│   └── index.py             # Serverless entry point - uses Plivo SDK (plivoxml)
│
├── .env                      # Environment variables (local only, not in git)
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
│   Phone Call ──► Plivo ──► Vercel/Flask ──► XML Response    │
│                              │                              │
│                    ┌─────────┴─────────┐                    │
│                    │                   │                    │
│               PostgreSQL            Redis                   │
│             (Call Logs)         (Sessions)                  │
│                                                             │
│   VOICE AI (Week 2):                                        │
│   Microphone ──► Whisper ──► GPT-4o ──► ElevenLabs ──► Speaker │
│      (VAD)       (STT)       (LLM)        (TTS)             │
│                                                             │
│   LIVEKIT PHONE-TO-AI (Day 5-7):                           │
│   Phone ──► Plivo ──► SIP Forward ──► LiveKit Cloud        │
│                                            │               │
│                    ┌───────────────────────┘               │
│                    ▼                                       │
│             AI Agent (Railway)                             │
│        Deepgram ──► GPT-4o ──► ElevenLabs                 │
│          (STT)      (LLM)       (TTS)                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Commands

```bash
# === WEEK 1: Telephony ===

# Run Flask server locally (IVR + API)
python3 week1/app.py

# Run folder scanner
python3 week1/folder_scanner.py

# Run Plivo checker
python3 week1/checker.py

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

# Run LiveKit voice agent (Day 5, REQUIRES Python 3.11)
python3.11 week2/livekit_agent.py dev

# Run SIP forward server (bridges Plivo to LiveKit)
python3 week2/sip_forward.py

# Run demo dashboard (Day 7)
python3 week2/dashboard.py

# === DEPLOYMENT ===

# Deploy to Vercel (Week 1 IVR)
vercel --prod

# Deploy to Railway (LiveKit Agent - Day 6)
cd week2 && railway up

# View Railway logs
railway logs
```

## Environment Variables

Required in `.env` (root directory) for local development:
```
PLIVO_AUTH_ID=xxx
PLIVO_AUTH_TOKEN=xxx
OPENAI_API_KEY=xxx          # Used for GPT + Whisper STT
ELEVENLABS_API_KEY=xxx      # Used for TTS
DEEPGRAM_API_KEY=xxx        # Used for real-time STT (Day 5)
SECRET_KEY=xxx              # Optional, for Flask sessions
REDIS_URL=redis://localhost:6379  # Local Redis
DATABASE_URL=sqlite:///local.db   # Local SQLite (or PostgreSQL URL)

# LiveKit (Day 5) - from cloud.livekit.io
LIVEKIT_API_KEY=xxx
LIVEKIT_API_SECRET=xxx
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_SIP_URI=sip:xxx.sip.livekit.cloud  # From LiveKit SIP Inbound Trunk
```

Vercel environment variables (auto-configured):
- `DATABASE_URL` - Vercel Postgres (Neon)
- `REDIS_URL` - Redis Cloud

## Vercel Production Endpoints

**Live URL**: https://demo-ivr.vercel.app

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/answer` | POST | **Plivo webhook** - incoming call handler |
| `/api/handle-input` | POST | **Plivo webhook** - digit input handler |
| `/api/health` | GET | Health check (Redis + PostgreSQL status) |
| `/api/call-logs` | GET | View all call logs (PostgreSQL) |
| `/api/log-call` | POST | Add a call log entry |
| `/api/call-history/<phone>` | GET | Call history for specific number |
| `/sessions` | GET | View active sessions (Redis) |
| `/calls` | GET/POST | Call log CRUD |
| `/health` | GET | System health status |

**Backward compatible routes** (also work):
- `/voice/incoming` → same as `/api/answer`
- `/voice/menu` → same as `/api/handle-input`

## Week 1: Local Development Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/voice/incoming` | POST | Plivo webhook - incoming call handler |
| `/voice/menu` | POST | Plivo webhook - menu selection handler |
| `/simulator` | GET | Web-based IVR simulator |
| `/call` | GET | Outbound call trigger UI |
| `/make-call` | POST | Initiate outbound call via Plivo |
| `/start-session/<caller_id>` | GET/POST | Start Redis session |
| `/get-session/<caller_id>` | GET | Get Redis session |
| `/list-sessions` | GET | List all Redis sessions |

## Data Storage

### PostgreSQL (Permanent - Call Logs)
- Stores all call records permanently
- Fields: `id`, `caller_number`, `call_status`, `created_at`
- View via: `curl https://demo-ivr.vercel.app/calls`

### Redis (Temporary - Active Sessions)
- Stores active call state during calls
- Auto-expires after 30 minutes (TTL)
- Tracks caller's current menu step
- View via: `curl https://demo-ivr.vercel.app/sessions`

**Note**: Redis is hosted on **Redis Cloud** (redislabs.com), not Vercel KV. View data via:
1. `/sessions` API endpoint
2. Redis Cloud dashboard at https://app.redislabs.com

## Deployment

### Vercel (Production)
- **Live URL**: https://demo-ivr.vercel.app
- **Entry point**: `api/index.py`
- **Database**: Vercel Postgres (Neon) - `DATABASE_URL`
- **Cache**: Redis Cloud - `REDIS_URL`

```bash
vercel --prod    # Deploy to production
vercel           # Deploy to preview
```

### Railway (LiveKit Agent - Day 6)
- **Platform**: railway.app
- **Service**: livekit-agent
- **Dockerfile**: `week2/Dockerfile`
- **Runs 24/7**: Agent handles phone calls without local machine

```bash
cd week2
railway login        # One-time auth
railway link         # Link to project
railway up           # Deploy
railway logs         # View logs
railway open         # Open dashboard
```

### Local Development
```bash
# Start Redis locally
brew services start redis

# Week 1: Flask IVR
python3 week1/app.py
ngrok http 5001

# Week 2: Pipecat IVR
python3.11 week2/pipecat_ivr.py
ngrok http 8000

# Week 2: LiveKit Agent (local dev)
python3.11 week2/livekit_agent.py dev
python3 week2/sip_forward.py  # In another terminal
ngrok http 5002               # Expose SIP forward
```

## Plivo Configuration

- **Console**: console.plivo.in (Indian account)
- **Phone Number**: +91 80354 53216 (Bangalore)
- **Application**: My-IVR
- **Answer URL**: `https://demo-ivr.vercel.app/api/answer` (POST)
- **Hangup URL**: `https://demo-ivr.vercel.app/voice/status` (POST)

### Plivo XML Guidelines
1. **Use Plivo SDK** (`plivoxml`) to generate XML - don't write raw XML strings
2. **Always use absolute URLs** in `action` attributes
3. **Use POST method** for GetDigits action URLs
4. **Don't use `voice` attribute** unless specifically needed

Example using Plivo SDK:
```python
from plivo import plivoxml

response = plivoxml.ResponseElement()
response.add(plivoxml.SpeakElement("Welcome to Acme Corp."))
get_digits = plivoxml.GetDigitsElement(
    action="https://demo-ivr.vercel.app/api/handle-input",
    method="POST",
    timeout=10,
    num_digits=1
)
get_digits.add(plivoxml.SpeakElement("Press 1 for Sales."))
response.add(get_digits)
return Response(response.to_string(), mimetype="application/xml")
```

## LiveKit AI Receptionist (Day 5-7)

The AI agent has these function calling capabilities:
- **check_order_status**: "Check order ORD-12345"
- **get_business_hours**: "What are your hours?"
- **lookup_product**: "How much is the widget?"
- **schedule_callback**: "Have someone call me back"
- **transfer_to_department**: "Transfer me to sales"
- **end_call**: "Goodbye" → confirms → hangs up

## Testing

- **IVR Simulator**: http://localhost:5001/simulator (test without real phone)
- **Call UI**: http://localhost:5001/call (trigger real outbound calls)
- **Voice Bot (text mode)**: `python3 week2/voice_bot.py` → choose mode 2
- **Pipecat Bot (full voice)**: `python3.11 week2/pipecat_bot.py`
- **LiveKit Playground**: https://agents-playground.livekit.io/
- **Demo Dashboard**: http://localhost:5003 (run `python3 week2/dashboard.py`)
- **Phone-to-AI**: Call +91 80354 53216

## Common Issues & Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| Busy tone on call | Invalid XML or unreachable webhook | Check URL is correct, use Plivo SDK |
| No audio on call | Raw XML strings | Use `plivoxml` module instead |
| Call cuts immediately | `voice` attribute not supported | Remove voice attribute or use SDK |
| Call history empty | Phone format mismatch | Query uses LIKE to match any format |
| Redis not in Vercel Storage | Using Redis Cloud | View at redislabs.com or `/sessions` |
| ElevenLabs 401 error | Deprecated model | Use `eleven_turbo_v2_5` |
| Pipecat SyntaxError | Python version too old | Use `python3.11` |

## Python Version Notes

| Directory | Python Version | Reason |
|-----------|----------------|--------|
| `week1/*` | 3.9+ | Standard Flask/OpenAI |
| `api/index.py` | 3.9+ | Vercel serverless |
| `week2/pipecat_*.py` | **3.11+** | Pipecat uses `match` statements |
| `week2/livekit_agent.py` | **3.11+** | LiveKit Agents SDK |
| `week2/llm.py`, `week2/speech.py` | 3.9+ | Standard OpenAI |
| `week2/sip_forward.py` | 3.9+ | Flask SIP bridge |
| `week2/dashboard.py` | 3.9+ | Flask demo dashboard |
