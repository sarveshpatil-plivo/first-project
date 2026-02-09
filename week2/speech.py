"""
Week 2, Day 2: Speech AI
- OpenAI Whisper: Speech-to-Text (STT) - Convert voice to text
- ElevenLabs: Text-to-Speech (TTS) - Convert text to voice
- Deepgram (optional): Alternative STT provider
"""

import os
import httpx
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# Initialize OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


# ============ 1. OPENAI WHISPER: Speech-to-Text ============

def transcribe_audio_whisper(audio_path):
    """
    Convert an audio file to text using OpenAI Whisper.
    Supports: mp3, mp4, mpeg, mpga, m4a, wav, webm
    """
    if not openai_client:
        raise Exception("OpenAI API key not found")

    with open(audio_path, "rb") as audio_file:
        response = openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="text"
        )

    return response


def transcribe_audio_whisper_detailed(audio_path):
    """
    Transcribe with additional details (timestamps, language detection).
    """
    if not openai_client:
        raise Exception("OpenAI API key not found")

    with open(audio_path, "rb") as audio_file:
        response = openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="verbose_json"
        )

    return {
        "text": response.text,
        "language": response.language,
        "duration": response.duration
    }


# ============ 1. DEEPGRAM: Speech-to-Text ============

def transcribe_audio_file(audio_path):
    """
    Convert an audio file to text using Deepgram.
    Supports: mp3, wav, m4a, flac, etc.
    """
    from deepgram import DeepgramClient, PrerecordedOptions

    client = DeepgramClient(DEEPGRAM_API_KEY)

    with open(audio_path, "rb") as audio_file:
        audio_data = audio_file.read()

    options = PrerecordedOptions(
        model="nova-2",        # Best accuracy model
        smart_format=True,     # Add punctuation
        language="en"          # Language
    )

    response = client.listen.prerecorded.v("1").transcribe_file(
        {"buffer": audio_data},
        options
    )

    # Extract transcript
    transcript = response.results.channels[0].alternatives[0].transcript
    return transcript


def transcribe_audio_url(audio_url):
    """
    Transcribe audio from a URL.
    """
    from deepgram import DeepgramClient, PrerecordedOptions

    client = DeepgramClient(DEEPGRAM_API_KEY)

    options = PrerecordedOptions(
        model="nova-2",
        smart_format=True,
        language="en"
    )

    response = client.listen.prerecorded.v("1").transcribe_url(
        {"url": audio_url},
        options
    )

    transcript = response.results.channels[0].alternatives[0].transcript
    return transcript


# ============ 2. ELEVENLABS: Text-to-Speech ============

# Popular ElevenLabs voice IDs
VOICES = {
    "rachel": "21m00Tcm4TlvDq8ikWAM",      # Female, calm
    "drew": "29vD33N1CtxCmqQRPOHJ",         # Male, professional
    "clyde": "2EiwWnXFnvU5JabPnv8n",        # Male, deep
    "sarah": "EXAVITQu4vr4xnSDxMaL",        # Female, soft
    "adam": "pNInz6obpgDQGcFmaJgB",         # Male, deep narrator
}


def text_to_speech(text, voice="rachel", output_path="output.mp3"):
    """
    Convert text to speech using ElevenLabs.
    Returns the path to the generated audio file.
    """
    voice_id = VOICES.get(voice, voice)  # Use name or direct ID

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

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

    response = httpx.post(url, json=data, headers=headers, timeout=30)

    if response.status_code == 200:
        with open(output_path, "wb") as f:
            f.write(response.content)
        return output_path
    else:
        raise Exception(f"ElevenLabs error: {response.status_code} - {response.text}")


def text_to_speech_stream(text, voice="rachel"):
    """
    Stream text-to-speech audio (for real-time playback).
    Yields audio chunks as they're generated.
    """
    voice_id = VOICES.get(voice, voice)

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"

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

    with httpx.stream("POST", url, json=data, headers=headers, timeout=30) as response:
        for chunk in response.iter_bytes():
            yield chunk


def list_voices():
    """
    List all available ElevenLabs voices.
    """
    url = "https://api.elevenlabs.io/v1/voices"
    headers = {"xi-api-key": ELEVENLABS_API_KEY}

    response = httpx.get(url, headers=headers)

    if response.status_code == 200:
        voices = response.json()["voices"]
        return [(v["name"], v["voice_id"]) for v in voices]
    else:
        raise Exception(f"Error: {response.status_code}")


# ============ 3. COMBINED: Full Voice Pipeline ============

def voice_to_voice(audio_path, process_func=None, use_whisper=True):
    """
    Full pipeline: Audio → Text → Process → Speech

    audio_path: Path to input audio file
    process_func: Optional function to process the transcript (e.g., send to LLM)
    use_whisper: Use OpenAI Whisper (True) or Deepgram (False)

    Returns: Path to output audio file
    """
    print("🎤 Transcribing audio...")
    if use_whisper:
        transcript = transcribe_audio_whisper(audio_path)
    else:
        transcript = transcribe_audio_file(audio_path)
    print(f"   Heard: '{transcript}'")

    if process_func:
        print("🤖 Processing with AI...")
        response_text = process_func(transcript)
    else:
        response_text = f"You said: {transcript}"
    print(f"   Response: '{response_text}'")

    print("🔊 Generating speech...")
    output_path = text_to_speech(response_text)
    print(f"   Saved to: {output_path}")

    return output_path


# ============ Demo Functions ============

def demo_tts():
    """Demo text-to-speech."""
    print("\n" + "="*50)
    print("DEMO 1: Text-to-Speech (ElevenLabs)")
    print("="*50)

    text = "Hello! Welcome to our company. Press 1 for sales, or press 2 for support."

    print(f"\nText: '{text}'")
    print("Generating audio...")

    output = text_to_speech(text, voice="rachel", output_path="demo_tts.mp3")
    print(f"✓ Audio saved to: {output}")
    print("  (Open demo_tts.mp3 to listen)")


def demo_stt_whisper():
    """Demo speech-to-text using OpenAI Whisper."""
    print("\n" + "="*50)
    print("DEMO 2: Speech-to-Text (OpenAI Whisper)")
    print("="*50)

    # First, create a sample audio file using ElevenLabs
    sample_text = "Hello, this is a test of the speech to text system. How are you doing today?"
    sample_audio = "sample_for_stt.mp3"

    print(f"\nCreating sample audio with ElevenLabs...")
    text_to_speech(sample_text, voice="rachel", output_path=sample_audio)
    print(f"✓ Created: {sample_audio}")

    print(f"\nTranscribing with OpenAI Whisper...")
    transcript = transcribe_audio_whisper(sample_audio)
    print(f"\n✓ Transcript: '{transcript}'")

    # Clean up
    os.remove(sample_audio)
    print(f"✓ Cleaned up temp file")


def demo_stt_deepgram():
    """Demo speech-to-text using Deepgram (if API key available)."""
    print("\n" + "="*50)
    print("DEMO: Speech-to-Text (Deepgram)")
    print("="*50)

    # Using a sample audio file from the web
    sample_url = "https://static.deepgram.com/examples/interview_speech-analytics.wav"

    print(f"\nTranscribing audio from URL...")
    print(f"URL: {sample_url[:50]}...")

    transcript = transcribe_audio_url(sample_url)
    print(f"\n✓ Transcript:\n{transcript[:500]}...")


def demo_voices():
    """Demo listing available voices."""
    print("\n" + "="*50)
    print("DEMO 3: Available Voices")
    print("="*50)

    print("\nFetching voice list from ElevenLabs...")
    try:
        voices = list_voices()
        print(f"\n✓ Found {len(voices)} voices:")
        for name, voice_id in voices[:10]:  # Show first 10
            print(f"  - {name}: {voice_id}")
    except Exception as e:
        print(f"\n⚠️ Could not fetch voice list: {e}")
        print("\nUsing built-in voice presets:")
        for name, voice_id in VOICES.items():
            print(f"  - {name}: {voice_id}")


if __name__ == "__main__":
    print("🎙️ Week 2, Day 2: Speech AI Demo")
    print("=================================")

    # Check for API keys
    has_openai = bool(OPENAI_API_KEY)
    has_deepgram = bool(DEEPGRAM_API_KEY)
    has_elevenlabs = bool(ELEVENLABS_API_KEY)

    print(f"\nAPI Keys Status:")
    print(f"  OPENAI_API_KEY:     {'✓ Found' if has_openai else '✗ Missing'}")
    print(f"  ELEVENLABS_API_KEY: {'✓ Found' if has_elevenlabs else '✗ Missing'}")
    print(f"  DEEPGRAM_API_KEY:   {'✓ Found' if has_deepgram else '○ Optional (using Whisper)'}")

    if not has_elevenlabs or not has_openai:
        print("\n❌ Missing required API keys (OpenAI and ElevenLabs).")
        exit(1)

    # Run TTS demo
    demo_tts()

    # Run STT demo with Whisper
    demo_stt_whisper()

    # Run voices demo
    demo_voices()

    print("\n" + "="*50)
    print("✅ All demos complete!")
    print("="*50)
