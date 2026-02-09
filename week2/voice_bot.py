"""
Week 2, Day 3: Voice Bot
A real-time voice assistant you can talk to.

Pipeline:
1. Record from microphone (or type text)
2. Transcribe with OpenAI Whisper
3. Process with OpenAI GPT
4. Speak with ElevenLabs
5. Play through speakers
"""

import os
import io
import wave
import tempfile
from dotenv import load_dotenv
from openai import OpenAI
import httpx

load_dotenv()

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# Initialize OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


# ============ Audio Recording ============

def record_audio(duration=5, sample_rate=16000):
    """
    Record audio from microphone.
    Returns: path to temporary WAV file
    """
    try:
        import pyaudio
    except ImportError:
        print("❌ PyAudio not installed. Install with: brew install portaudio && pip3 install pyaudio")
        return None

    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1

    p = pyaudio.PyAudio()

    print(f"🎤 Recording for {duration} seconds... Speak now!")

    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=sample_rate,
        input=True,
        frames_per_buffer=CHUNK
    )

    frames = []
    for _ in range(0, int(sample_rate / CHUNK * duration)):
        data = stream.read(CHUNK)
        frames.append(data)

    print("✓ Recording complete")

    stream.stop_stream()
    stream.close()
    p.terminate()

    # Save to temporary WAV file
    temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    with wave.open(temp_file.name, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(sample_rate)
        wf.writeframes(b''.join(frames))

    return temp_file.name


# ============ Speech-to-Text (OpenAI Whisper) ============

def transcribe(audio_path):
    """
    Convert audio file to text using OpenAI Whisper.
    """
    if not openai_client:
        raise Exception("OpenAI API key not configured")

    with open(audio_path, "rb") as audio_file:
        response = openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="text"
        )

    return response.strip()


# ============ LLM Processing (OpenAI) ============

def get_ai_response(user_message, conversation_history=None):
    """
    Get AI response using OpenAI.
    """
    if not openai_client:
        raise Exception("OpenAI API key not configured")

    system_prompt = """You are a friendly voice assistant. Keep your responses brief and conversational
(2-3 sentences max). You're having a spoken conversation, so be natural and don't use
bullet points or formatting."""

    messages = [{"role": "system", "content": system_prompt}]

    if conversation_history:
        messages.extend(conversation_history)

    messages.append({"role": "user", "content": user_message})

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )

    return response.choices[0].message.content


# ============ Text-to-Speech (ElevenLabs) ============

def speak(text, voice_id="21m00Tcm4TlvDq8ikWAM"):
    """
    Convert text to speech and play it.
    voice_id: rachel (default), or any ElevenLabs voice ID
    """
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
        # Save to temp file and play
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(response.content)
            temp_path = f.name

        play_audio(temp_path)
        os.unlink(temp_path)  # Clean up
    else:
        print(f"❌ ElevenLabs error: {response.status_code} - {response.text}")


def play_audio(file_path):
    """
    Play an audio file through speakers.
    """
    import subprocess
    import platform

    system = platform.system()

    if system == "Darwin":  # macOS
        subprocess.run(["afplay", file_path], check=True)
    elif system == "Linux":
        subprocess.run(["aplay", file_path], check=True)
    elif system == "Windows":
        subprocess.run(["start", file_path], shell=True, check=True)


# ============ Main Voice Bot Loop (Full Voice) ============

def run_voice_bot():
    """
    Main voice bot loop - continuously listens and responds.
    Requires microphone + PyAudio.
    """
    print("\n" + "="*50)
    print("🤖 VOICE BOT - Speak to interact!")
    print("="*50)
    print("\nCommands:")
    print("  - Press Enter, then speak for 5 seconds")
    print("  - Say 'goodbye' or 'exit' to quit")
    print("  - Press Ctrl+C to force quit")
    print("\n")

    conversation_history = []

    while True:
        try:
            # 1. Record user's voice
            input("Press Enter to start recording (or Ctrl+C to quit)...")
            audio_path = record_audio(duration=5)

            if not audio_path:
                continue

            # 2. Transcribe to text
            print("📝 Transcribing with Whisper...")
            user_text = transcribe(audio_path)
            print(f"   You said: '{user_text}'")

            # Clean up temp file
            os.unlink(audio_path)

            if not user_text.strip():
                print("   (No speech detected, try again)")
                continue

            # Check for exit commands
            if any(word in user_text.lower() for word in ['goodbye', 'exit', 'quit', 'bye']):
                print("\n👋 Goodbye!")
                speak("Goodbye! Have a great day!")
                break

            # 3. Get AI response
            print("🤔 Thinking...")
            ai_response = get_ai_response(user_text, conversation_history)
            print(f"   AI: '{ai_response}'")

            # Update conversation history
            conversation_history.append({"role": "user", "content": user_text})
            conversation_history.append({"role": "assistant", "content": ai_response})

            # Keep history manageable (last 10 exchanges)
            if len(conversation_history) > 20:
                conversation_history = conversation_history[-20:]

            # 4. Speak the response
            print("🔊 Speaking...")
            speak(ai_response)

            print("\n" + "-"*30 + "\n")

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            continue


# ============ Text Mode (No Microphone) ============

def run_text_mode():
    """
    Text-to-voice mode - type your messages, hear AI responses.
    No microphone needed.
    """
    print("\n" + "="*50)
    print("🤖 VOICE BOT (Text Mode)")
    print("="*50)
    print("\nType your messages and hear AI respond!")
    print("Type 'quit' to exit.\n")

    conversation_history = []

    while True:
        try:
            user_text = input("You: ").strip()

            if not user_text:
                continue

            if user_text.lower() in ['quit', 'exit', 'bye', 'goodbye']:
                print("\n👋 Goodbye!")
                speak("Goodbye! Have a great day!")
                break

            # Get AI response
            print("🤔 Thinking...")
            ai_response = get_ai_response(user_text, conversation_history)
            print(f"AI: {ai_response}")

            # Update history
            conversation_history.append({"role": "user", "content": user_text})
            conversation_history.append({"role": "assistant", "content": ai_response})

            # Keep history manageable
            if len(conversation_history) > 20:
                conversation_history = conversation_history[-20:]

            # Speak the response
            print("🔊 Speaking...")
            speak(ai_response)
            print()

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            continue


# ============ Entry Point ============

if __name__ == "__main__":
    print("🎙️ Week 2, Day 3: Voice Bot")
    print("============================")

    # Check API keys
    print(f"\nAPI Keys Status:")
    print(f"  OPENAI_API_KEY:     {'✓ Found' if OPENAI_API_KEY else '✗ Missing'}")
    print(f"  ELEVENLABS_API_KEY: {'✓ Found' if ELEVENLABS_API_KEY else '✗ Missing'}")

    if not OPENAI_API_KEY or not ELEVENLABS_API_KEY:
        print("\n❌ Both API keys are required.")
        print("Add them to your .env file:")
        print("  OPENAI_API_KEY=your_key")
        print("  ELEVENLABS_API_KEY=your_key")
        exit(1)

    # Check for PyAudio
    has_pyaudio = False
    try:
        import pyaudio
        has_pyaudio = True
    except ImportError:
        pass

    print(f"  PyAudio:            {'✓ Found' if has_pyaudio else '○ Not installed (text mode only)'}")

    print("\nChoose mode:")
    print("  1. Full voice mode (speak ↔ listen) " + ("" if has_pyaudio else "- requires PyAudio"))
    print("  2. Text mode (type → listen)")

    choice = input("\nEnter 1 or 2: ").strip()

    if choice == "1":
        if not has_pyaudio:
            print("\n❌ Full voice mode requires PyAudio.")
            print("Install with: brew install portaudio && pip3 install pyaudio")
        else:
            run_voice_bot()
    else:
        run_text_mode()
