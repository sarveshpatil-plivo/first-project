# Voice IVR Project

An enterprise-grade Voice IVR platform powered by AI and cloud telephony.

## Features

- **Week 1**: Flask IVR with Plivo telephony, Redis sessions, PostgreSQL call logs
- **Week 2**: Voice AI with Whisper STT, GPT-4, ElevenLabs TTS, Pipecat integration

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run Week 1 Flask IVR
python3 week1/app.py

# Run Week 2 Voice AI (requires Python 3.11)
python3.11 week2/pipecat_ivr.py
```

## Project Structure

```
├── week1/          # Telephony (Flask + Plivo)
├── week2/          # Voice AI (Pipecat + OpenAI + ElevenLabs)
├── api/            # Vercel deployment
└── requirements.txt
```

## Environment Variables

Create a `.env` file with:
```
PLIVO_AUTH_ID=xxx
PLIVO_AUTH_TOKEN=xxx
OPENAI_API_KEY=xxx
ELEVENLABS_API_KEY=xxx
```
