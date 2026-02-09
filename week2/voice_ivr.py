"""
Week 2, Day 5: Voice IVR Integration
Connects Plivo phone calls to AI voice bot via WebSocket.

Architecture:
  Phone Call → Plivo → WebSocket → This Server → AI Pipeline → Audio back to caller

Pipeline:
  Audio In → Whisper STT → GPT-4o → ElevenLabs TTS → Audio Out
"""

import os
import json
import base64
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import Response
import uvicorn

load_dotenv()

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# Vercel URL for production
VERCEL_URL = "https://demo-ivr.vercel.app"

app = FastAPI(title="Voice IVR Integration")


# ============ Plivo XML Endpoints ============

@app.get("/")
def health():
    """Health check."""
    return {"status": "ok", "service": "Voice IVR Integration"}


@app.post("/voice/ai")
async def voice_ai_handler(request: Request):
    """
    Plivo webhook - starts AI voice conversation.
    Returns XML that establishes WebSocket connection for audio streaming.
    """
    # Get the host for WebSocket URL
    host = request.headers.get("host", "localhost:8000")

    # Use wss:// for production, ws:// for local
    ws_protocol = "wss" if "vercel" in host or "ngrok" in host else "ws"
    ws_url = f"{ws_protocol}://{host}/ws/audio"

    xml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak>Connecting you to our AI assistant. Please wait.</Speak>
    <Stream streamTimeout="3600" keepCallAlive="true" bidirectional="true" contentType="audio/x-mulaw;rate=8000">
        {ws_url}
    </Stream>
</Response>"""

    return Response(content=xml_response, media_type="application/xml")


# ============ WebSocket Audio Handler ============

class ConversationState:
    """Tracks conversation state for a call."""
    def __init__(self):
        self.messages = [
            {
                "role": "system",
                "content": """You are a friendly AI assistant on a phone call. Keep responses brief
(1-2 sentences). You're having a spoken conversation - be natural, don't use bullet points.
If the caller says goodbye, wish them well and end naturally."""
            }
        ]
        self.audio_buffer = bytearray()
        self.stream_id = None


# Store active conversations
conversations = {}


@app.websocket("/ws/audio")
async def websocket_audio_handler(websocket: WebSocket):
    """
    WebSocket endpoint for Plivo audio streaming.
    Receives audio from caller, processes with AI, sends audio back.
    """
    await websocket.accept()

    state = ConversationState()
    stream_id = None

    print("\n" + "="*50)
    print("NEW CALL CONNECTED")
    print("="*50)

    try:
        while True:
            # Receive message from Plivo
            data = await websocket.receive_text()
            message = json.loads(data)

            event = message.get("event")

            if event == "start":
                # Connection established
                stream_id = message.get("streamId")
                state.stream_id = stream_id
                conversations[stream_id] = state
                print(f"Stream started: {stream_id}")

            elif event == "media":
                # Audio chunk received
                media = message.get("media", {})
                payload = media.get("payload", "")

                if payload:
                    # Decode base64 audio and add to buffer
                    audio_data = base64.b64decode(payload)
                    state.audio_buffer.extend(audio_data)

                    # Process when we have enough audio (~2 seconds at 8kHz)
                    if len(state.audio_buffer) >= 16000:
                        await process_audio_chunk(websocket, state)

            elif event == "stop":
                # Stream ended
                print(f"Stream stopped: {stream_id}")
                if stream_id in conversations:
                    del conversations[stream_id]
                break

            elif event == "dtmf":
                # Keypress detected
                digit = message.get("digit")
                print(f"DTMF received: {digit}")

    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        if stream_id and stream_id in conversations:
            del conversations[stream_id]
        print("Call disconnected")


async def process_audio_chunk(websocket: WebSocket, state: ConversationState):
    """
    Process accumulated audio:
    1. Convert to text (Whisper STT)
    2. Get AI response (GPT)
    3. Convert to speech (ElevenLabs TTS)
    4. Send back to caller
    """
    import httpx
    from openai import OpenAI

    # Get audio from buffer and clear it
    audio_data = bytes(state.audio_buffer)
    state.audio_buffer.clear()

    try:
        # 1. Speech-to-Text with Whisper
        client = OpenAI(api_key=OPENAI_API_KEY)

        # Convert mulaw to wav for Whisper
        wav_audio = mulaw_to_wav(audio_data)

        # Transcribe
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=("audio.wav", wav_audio, "audio/wav"),
            response_format="text"
        )

        if not transcript.strip():
            return  # No speech detected

        print(f"Caller: {transcript}")

        # 2. Get AI response
        state.messages.append({"role": "user", "content": transcript})

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=state.messages
        )

        ai_response = response.choices[0].message.content
        state.messages.append({"role": "assistant", "content": ai_response})

        # Keep conversation history manageable
        if len(state.messages) > 12:
            state.messages = state.messages[:1] + state.messages[-10:]

        print(f"AI: {ai_response}")

        # 3. Text-to-Speech with ElevenLabs
        tts_audio = await text_to_speech_mulaw(ai_response)

        # 4. Send audio back to caller
        if tts_audio:
            await send_audio_to_plivo(websocket, tts_audio, state.stream_id)

    except Exception as e:
        print(f"Processing error: {e}")


def mulaw_to_wav(mulaw_data: bytes) -> bytes:
    """Convert mulaw audio to WAV format for Whisper."""
    import struct
    import io
    import wave

    # Mulaw decoding table
    def decode_mulaw(byte):
        byte = ~byte
        sign = (byte & 0x80) >> 7
        exponent = (byte & 0x70) >> 4
        mantissa = byte & 0x0F
        sample = (mantissa << 3) + 0x84
        sample <<= exponent
        sample -= 0x84
        return -sample if sign else sample

    # Decode mulaw to PCM
    pcm_data = []
    for byte in mulaw_data:
        pcm_data.append(decode_mulaw(byte))

    # Create WAV file in memory
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)  # 16-bit
        wav.setframerate(8000)
        wav.writeframes(struct.pack(f'<{len(pcm_data)}h', *pcm_data))

    wav_buffer.seek(0)
    return wav_buffer.read()


async def text_to_speech_mulaw(text: str) -> bytes:
    """Convert text to mulaw audio using ElevenLabs."""
    import httpx

    url = "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM"

    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY
    }

    data = {
        "text": text,
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=data, headers=headers, timeout=30)

        if response.status_code == 200:
            # Convert MP3 to mulaw (simplified - in production use proper conversion)
            mp3_audio = response.content
            return mp3_to_mulaw(mp3_audio)
        else:
            print(f"TTS error: {response.status_code}")
            return None


def mp3_to_mulaw(mp3_data: bytes) -> bytes:
    """Convert MP3 to mulaw format for Plivo."""
    # This is a simplified placeholder
    # In production, use pydub or ffmpeg for proper conversion
    # For now, return empty (audio won't play but won't crash)

    try:
        from pydub import AudioSegment
        import io

        # Load MP3
        audio = AudioSegment.from_mp3(io.BytesIO(mp3_data))

        # Convert to mulaw
        audio = audio.set_frame_rate(8000).set_channels(1)

        # Export as raw mulaw
        buffer = io.BytesIO()
        audio.export(buffer, format="wav", parameters=["-acodec", "pcm_mulaw"])

        return buffer.getvalue()
    except ImportError:
        print("Warning: pydub not installed. Audio conversion skipped.")
        return b""


async def send_audio_to_plivo(websocket: WebSocket, audio_data: bytes, stream_id: str):
    """Send audio back to Plivo via WebSocket."""
    # Plivo expects base64-encoded audio in specific format
    chunk_size = 640  # ~80ms of audio at 8kHz

    for i in range(0, len(audio_data), chunk_size):
        chunk = audio_data[i:i + chunk_size]

        message = {
            "event": "playAudio",
            "media": {
                "payload": base64.b64encode(chunk).decode("utf-8")
            }
        }

        await websocket.send_text(json.dumps(message))
        await asyncio.sleep(0.08)  # Pace the audio


# ============ Integration with Existing IVR ============

@app.post("/voice/incoming")
async def incoming_call(request: Request):
    """
    Updated incoming call handler with AI option.
    """
    host = request.headers.get("host", "localhost:8000")
    base_url = f"https://{host}" if "vercel" in host or "ngrok" in host else f"http://{host}"

    xml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak>Welcome to our AI-powered service.</Speak>
    <GetDigits action="{base_url}/voice/menu" method="POST" timeout="10" numDigits="1">
        <Speak>Press 1 for Sales. Press 2 for Support. Press 3 to speak with our AI assistant.</Speak>
    </GetDigits>
    <Speak>We didn't receive any input. Goodbye.</Speak>
</Response>"""

    return Response(content=xml_response, media_type="application/xml")


@app.post("/voice/menu")
async def menu_handler(request: Request):
    """
    Menu handler with AI option.
    """
    form_data = await request.form()
    digits = form_data.get("Digits", "")

    host = request.headers.get("host", "localhost:8000")
    base_url = f"https://{host}" if "vercel" in host or "ngrok" in host else f"http://{host}"
    ws_protocol = "wss" if "vercel" in host or "ngrok" in host else "ws"
    ws_url = f"{ws_protocol}://{host}/ws/audio"

    if digits == "1":
        xml_response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak>Connecting you to Sales. Please hold.</Speak>
</Response>"""
    elif digits == "2":
        xml_response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak>Connecting you to Support. Please hold.</Speak>
</Response>"""
    elif digits == "3":
        # Connect to AI assistant
        xml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak>Connecting you to our AI assistant.</Speak>
    <Stream streamTimeout="3600" keepCallAlive="true" bidirectional="true" contentType="audio/x-mulaw;rate=8000">
        {ws_url}
    </Stream>
</Response>"""
    else:
        xml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak>Invalid option.</Speak>
    <GetDigits action="{base_url}/voice/menu" method="POST" timeout="10" numDigits="1">
        <Speak>Press 1 for Sales. Press 2 for Support. Press 3 for AI assistant.</Speak>
    </GetDigits>
</Response>"""

    return Response(content=xml_response, media_type="application/xml")


# ============ Entry Point ============

if __name__ == "__main__":
    print("="*60)
    print("VOICE IVR INTEGRATION SERVER")
    print("="*60)
    print(f"\nAPI Keys:")
    print(f"  OPENAI_API_KEY:     {'Found' if OPENAI_API_KEY else 'Missing'}")
    print(f"  ELEVENLABS_API_KEY: {'Found' if ELEVENLABS_API_KEY else 'Missing'}")

    print(f"\nEndpoints:")
    print(f"  POST /voice/incoming  - IVR entry point")
    print(f"  POST /voice/menu      - Menu handler")
    print(f"  POST /voice/ai        - Direct AI connection")
    print(f"  WS   /ws/audio        - Audio streaming WebSocket")

    print(f"\nTo test locally:")
    print(f"  1. Run: python3 voice_ivr.py")
    print(f"  2. Expose with ngrok: ngrok http 8000")
    print(f"  3. Update Plivo webhook to ngrok URL")

    print("\n" + "="*60)
    print("Starting server on http://localhost:8000")
    print("="*60 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8000)
