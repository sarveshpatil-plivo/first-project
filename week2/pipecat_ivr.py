"""
Week 2, Day 5: Pipecat IVR Integration
Connects Plivo phone calls to Pipecat voice bot via WebSocket.

This uses Pipecat's built-in Plivo transport for cleaner integration.

Architecture:
  Phone Call → Plivo → WebSocket → Pipecat Pipeline → Audio back to caller

Run with Python 3.11:
  python3.11 pipecat_ivr.py
"""

import os
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import Response
import uvicorn

load_dotenv()

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
PLIVO_AUTH_ID = os.getenv("PLIVO_AUTH_ID")
PLIVO_AUTH_TOKEN = os.getenv("PLIVO_AUTH_TOKEN")

app = FastAPI(title="Pipecat IVR Integration")


# ============ KNOWLEDGE BASE ============
# Add your company info, FAQs, product details here

KNOWLEDGE_BASE = {
    # Company Information
    "business_hours": {
        "keywords": ["hours", "open", "close", "timing", "when are you open", "working hours"],
        "answer": "We're open Monday through Friday from 9 AM to 6 PM, and Saturday from 10 AM to 4 PM. We're closed on Sundays."
    },
    "location": {
        "keywords": ["address", "location", "where", "office", "visit", "directions"],
        "answer": "Our office is located at 123 Tech Street, Koramangala, Bangalore. We're near the Metro station."
    },
    "contact": {
        "keywords": ["contact", "email", "phone", "reach", "call", "support email"],
        "answer": "You can reach us by email at support@techcorp.com or call our support line at 1800-123-4567."
    },

    # Products & Pricing
    "pricing": {
        "keywords": ["price", "cost", "pricing", "plans", "subscription", "how much", "rates"],
        "answer": "We have three plans: Basic at $9.99 per month with 10GB storage, Pro at $19.99 per month with 100GB storage, and Enterprise with custom pricing for unlimited storage."
    },
    "basic_plan": {
        "keywords": ["basic plan", "starter", "cheapest", "entry level"],
        "answer": "Our Basic plan is $9.99 per month. It includes 10GB storage, email support, and access to core features. Great for individuals."
    },
    "pro_plan": {
        "keywords": ["pro plan", "professional", "premium"],
        "answer": "Our Pro plan is $19.99 per month. It includes 100GB storage, priority support, advanced analytics, and API access. Perfect for small teams."
    },
    "enterprise_plan": {
        "keywords": ["enterprise", "business", "corporate", "custom"],
        "answer": "Our Enterprise plan has custom pricing based on your needs. It includes unlimited storage, dedicated support, custom integrations, and SLA guarantees. Contact sales for a quote."
    },

    # Policies
    "return_policy": {
        "keywords": ["return", "refund", "money back", "cancel", "cancellation"],
        "answer": "We offer a 30-day money-back guarantee. If you're not satisfied, contact support within 30 days of purchase for a full refund. No questions asked."
    },
    "shipping": {
        "keywords": ["shipping", "delivery", "how long", "ship time", "when will i get"],
        "answer": "Standard shipping takes 3 to 5 business days. Express shipping is available for 1 to 2 day delivery at an additional cost."
    },
    "warranty": {
        "keywords": ["warranty", "guarantee", "broken", "defect", "repair"],
        "answer": "All our products come with a 1-year warranty covering manufacturing defects. Extended warranty options are available at checkout."
    },

    # Technical Support
    "reset_password": {
        "keywords": ["password", "reset", "forgot", "login", "can't login", "locked out"],
        "answer": "To reset your password, go to the login page and click 'Forgot Password'. Enter your email and we'll send you a reset link. The link expires in 24 hours."
    },
    "account_setup": {
        "keywords": ["setup", "get started", "create account", "sign up", "register"],
        "answer": "To create an account, visit our website and click 'Sign Up'. Enter your email, create a password, and verify your email. Setup takes less than 2 minutes."
    },
    "technical_issues": {
        "keywords": ["not working", "bug", "error", "problem", "issue", "broken", "help"],
        "answer": "I'm sorry you're experiencing issues. For technical problems, please email support@techcorp.com with details of the issue, or call our tech support at 1800-123-4567 option 2."
    },

    # Sales & Orders
    "order_status": {
        "keywords": ["order status", "track", "where is my order", "order number", "tracking"],
        "answer": "To check your order status, visit our website and go to 'My Orders', or give me your order number and I can look it up for you."
    },
    "bulk_discount": {
        "keywords": ["bulk", "discount", "wholesale", "volume", "many licenses"],
        "answer": "Yes, we offer bulk discounts for orders of 10 or more licenses. Contact our sales team at sales@techcorp.com for a custom quote."
    },
    "payment_methods": {
        "keywords": ["payment", "pay", "credit card", "paypal", "how to pay"],
        "answer": "We accept all major credit cards, PayPal, and bank transfers for annual plans. Enterprise customers can also pay by invoice."
    },
}


def search_knowledge_base(query: str) -> str:
    """
    Search the knowledge base for relevant information.
    Returns the best matching answer or a fallback message.
    """
    query_lower = query.lower()
    best_match = None
    best_score = 0

    for topic, data in KNOWLEDGE_BASE.items():
        score = 0
        for keyword in data["keywords"]:
            if keyword in query_lower:
                # Longer keyword matches are better
                score += len(keyword)

        if score > best_score:
            best_score = score
            best_match = data["answer"]

    if best_match:
        return best_match
    else:
        return None  # No match found


# Function calling tools for OpenAI
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "Search the company knowledge base for information about products, pricing, policies, hours, support, etc. Use this when the user asks a question about the company or its services.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The user's question or topic to search for"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_order",
            "description": "Look up the status of an order by order ID",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The order ID to look up"
                    }
                },
                "required": ["order_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "schedule_callback",
            "description": "Schedule a callback from a human agent",
            "parameters": {
                "type": "object",
                "properties": {
                    "department": {
                        "type": "string",
                        "enum": ["sales", "support", "billing"],
                        "description": "Which department should call back"
                    },
                    "preferred_time": {
                        "type": "string",
                        "description": "When the customer prefers to be called back"
                    }
                },
                "required": ["department"]
            }
        }
    }
]


def execute_function(function_name: str, arguments: dict) -> str:
    """Execute a function call and return the result."""
    if function_name == "search_knowledge":
        result = search_knowledge_base(arguments.get("query", ""))
        if result:
            return result
        else:
            return "I don't have specific information about that in my knowledge base. Would you like me to connect you with a human agent?"

    elif function_name == "lookup_order":
        order_id = arguments.get("order_id", "unknown")
        # Mock order lookup
        return f"Order {order_id} is currently in transit and expected to be delivered within 2-3 business days. You'll receive a tracking email shortly."

    elif function_name == "schedule_callback":
        department = arguments.get("department", "support")
        preferred_time = arguments.get("preferred_time", "as soon as possible")
        # Mock callback scheduling
        return f"I've scheduled a callback from our {department} team for {preferred_time}. They'll call you at this number. Is there anything else I can help with?"

    else:
        return "I'm sorry, I couldn't process that request."


# ============ Pipecat Pipeline ============

async def run_voice_pipeline(websocket: WebSocket, stream_id: str, call_id: str):
    """
    Run the Pipecat voice pipeline for a phone call.
    """
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.pipeline.task import PipelineTask, PipelineParams
    from pipecat.transports.websocket.fastapi import (
        FastAPIWebsocketTransport,
        FastAPIWebsocketParams,
    )
    from pipecat.serializers.plivo import PlivoFrameSerializer
    from pipecat.services.openai.llm import OpenAILLMService
    from pipecat.services.openai.stt import OpenAISTTService
    from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
    from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext

    print(f"\nStarting pipeline for call: {call_id}")

    # Create Plivo serializer for audio format conversion
    serializer = PlivoFrameSerializer(
        stream_id=stream_id,
        call_id=call_id,
        auth_id=PLIVO_AUTH_ID,
        auth_token=PLIVO_AUTH_TOKEN,
    )

    # Create transport for WebSocket audio
    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            serializer=serializer,
        ),
    )

    # Create STT service (Whisper)
    stt = OpenAISTTService(api_key=OPENAI_API_KEY)

    # Create LLM service
    llm = OpenAILLMService(
        api_key=OPENAI_API_KEY,
        model="gpt-4o-mini"
    )

    # Create TTS service (ElevenLabs)
    tts = ElevenLabsTTSService(
        api_key=ELEVENLABS_API_KEY,
        voice_id="21m00Tcm4TlvDq8ikWAM",  # Rachel
        model="eleven_turbo_v2_5",
        output_format="ulaw_8000"  # Plivo requires mulaw 8kHz
    )

    # Create conversation context
    messages = [
        {
            "role": "system",
            "content": """You are a friendly AI phone assistant. Keep responses very brief
(1-2 sentences max). You're on a phone call - be natural and conversational.
Don't use bullet points or formatting. If they say goodbye, say a brief farewell."""
        }
    ]

    context = OpenAILLMContext(messages)
    context_aggregator = llm.create_context_aggregator(context)

    # Build the pipeline
    pipeline = Pipeline([
        transport.input(),           # Audio from phone
        stt,                         # Speech-to-text
        context_aggregator.user(),   # Collect user speech
        llm,                         # Process with LLM
        tts,                         # Convert to speech
        transport.output(),          # Audio back to phone
        context_aggregator.assistant()
    ])

    # Run the pipeline
    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=8000,   # Plivo uses 8kHz
            audio_out_sample_rate=8000,
            allow_interruptions=True,    # Allow caller to interrupt
        )
    )

    runner = PipelineRunner()

    try:
        await runner.run(task)
    except Exception as e:
        if "cancelled" not in str(e).lower():
            print(f"Pipeline error: {e}")


# ============ WebSocket Handler ============

@app.websocket("/ws/audio")
async def websocket_handler(websocket: WebSocket):
    """
    WebSocket endpoint for Plivo audio streaming.
    Handles Plivo's JSON message format and processes audio.
    """
    await websocket.accept()

    import json
    import base64
    from openai import OpenAI
    import httpx
    import io
    import wave
    import struct
    import sys

    print(f"\n{'='*50}", flush=True)
    print(f"WEBSOCKET CONNECTED", flush=True)
    print(f"{'='*50}\n", flush=True)

    stream_id = None
    call_id = None
    audio_buffer = bytearray()
    is_speaking = False  # True while AI is speaking
    is_interrupted = False  # True if user interrupted AI
    last_response_time = 0  # Timestamp of last AI response
    last_audio_time = 0  # Timestamp of last audio chunk with speech
    last_silence_time = 0  # Timestamp when silence started
    MIN_PAUSE_AFTER_SPEECH = 1.5  # Wait 1.5 seconds after AI speaks before processing
    SILENCE_DURATION_TO_PROCESS = 1.2  # Process after 1.2s of silence (user stopped talking)
    MIN_AUDIO_LENGTH = 4000  # Minimum audio to process (0.5 second)
    ENERGY_THRESHOLD = 500  # Audio energy threshold for speech detection (tune this)

    # Track speech state
    user_is_speaking = False
    speech_start_time = 0

    # Goodbye flow state
    pending_goodbye = False  # True when we've asked "any other questions?"
    NO_RESPONSES = ["no", "nope", "no thanks", "nothing", "that's all", "i'm good",
                    "no i'm good", "nope that's it", "no questions", "nothing else",
                    "all good", "i'm fine", "no thank you"]

    def calculate_audio_energy(audio_chunk):
        """Calculate the energy/volume of audio chunk to detect speech."""
        if len(audio_chunk) == 0:
            return 0
        # Decode mulaw and calculate RMS energy
        total = 0
        for byte in audio_chunk:
            # Simple mulaw decode for energy calculation
            byte = ~byte & 0xFF
            sign = (byte & 0x80)
            exponent = (byte >> 4) & 0x07
            mantissa = byte & 0x0F
            sample = ((mantissa << 3) + 0x84) << exponent
            sample -= 0x84
            if sign:
                sample = -sample
            total += sample * sample
        return (total / len(audio_chunk)) ** 0.5  # RMS

    # Exit phrases - must be CLEAR exit intent (not just "thank you" or "thanks")
    EXIT_PHRASES = [
        # Direct goodbyes (these are clear exit signals)
        "goodbye", "bye", "bye bye", "good bye", "bye for now", "bye now",
        # Clear completion phrases
        "that's all", "that's it", "nothing else", "no more questions",
        "i'm done", "all done", "we're done", "that's everything",
        # Thank you + EXPLICIT bye/done (not just "thank you" alone)
        "thank you bye", "thanks bye", "thank you goodbye", "thanks that's all",
        "thanks i'm done", "thank you that's it", "thanks i'm good now",
        # Clear ending intent
        "end call", "hang up", "disconnect", "end the call", "cut the call",
        "gotta go", "have to go", "need to go", "i'll let you go",
        # Informal clear exits
        "okay bye", "alright bye", "okay that's all", "alright that's it",
        "i think i'm done", "i think that's all", "i guess that's it",
        "nope that's all", "no that's it", "no i'm done",
    ]

    # NOT exit phrases - these are just acknowledgments (not exit signals)
    NOT_EXIT_PHRASES = [
        "thank you", "thanks", "thank you so much", "thanks a lot", "thanks so much",
        "okay", "ok", "got it", "alright", "cool", "great", "perfect", "awesome",
        "i see", "i understand", "understood", "makes sense", "that helps",
        "wonderful", "excellent", "fantastic", "amazing", "sure", "right"
    ]

    conversation = [
        {
            "role": "system",
            "content": """You are a friendly AI phone assistant for TechCorp on a voice call.

CAPABILITIES:
- You have access to a knowledge base with company info, pricing, policies, and FAQs
- You can look up order status if the customer provides an order ID
- You can schedule callbacks from human agents (sales, support, or billing)

RULES:
1. Keep responses brief (1-2 sentences max) - this is a phone call, not text.
2. Be natural and conversational. No bullet points or formatting.
3. Use the search_knowledge function when users ask about company info, pricing, hours, policies, etc.
4. Use lookup_order when they ask about an order (ask for order ID if not provided).
5. Use schedule_callback if they want to speak to a human or need help you can't provide.
6. If the user's message seems garbled or unclear, ask them to repeat.
7. Don't ask "how can I help" repeatedly.

EXIT DETECTION (IMPORTANT):
- ONLY respond with [EXIT_INTENT_DETECTED] when the user CLEARLY wants to END the call
- Examples that ARE exit intent: "bye", "goodbye", "I'm done", "that's all I needed", "nothing else thanks", "okay bye", "gotta go"
- Examples that are NOT exit intent: "thank you" (alone), "thanks", "okay", "got it" - these are just acknowledgments, NOT exits
- When user just says "thank you" after you answered, say "You're welcome! Is there anything else I can help with?"
- Only trigger exit when they explicitly indicate they want to leave"""
        }
    ]

    async def send_audio_to_plivo(audio_base64: str):
        """Send audio back to the caller."""
        message = {
            "event": "playAudio",
            "media": {
                "contentType": "audio/x-mulaw",
                "sampleRate": 8000,
                "payload": audio_base64
            }
        }
        await websocket.send_text(json.dumps(message))

    def mulaw_decode(mulaw_byte):
        """Decode a single mulaw byte to PCM."""
        mulaw_byte = ~mulaw_byte & 0xFF
        sign = (mulaw_byte & 0x80)
        exponent = (mulaw_byte >> 4) & 0x07
        mantissa = mulaw_byte & 0x0F
        sample = ((mantissa << 3) + 0x84) << exponent
        sample -= 0x84
        return -sample if sign else sample

    def pcm_to_mulaw(pcm_sample):
        """Encode a PCM sample to mulaw."""
        MULAW_MAX = 0x1FFF
        MULAW_BIAS = 33

        sign = 0
        if pcm_sample < 0:
            sign = 0x80
            pcm_sample = -pcm_sample

        pcm_sample = min(pcm_sample + MULAW_BIAS, MULAW_MAX)

        exponent = 7
        for exp in range(8):
            if pcm_sample < (1 << (exp + 8)):
                exponent = exp
                break

        mantissa = (pcm_sample >> (exponent + 3)) & 0x0F
        mulaw_byte = ~(sign | (exponent << 4) | mantissa) & 0xFF
        return mulaw_byte

    try:
        print("Waiting for Plivo messages...", flush=True)
        while True:
            try:
                data = await websocket.receive_text()
                print(f"Received: {data[:100]}...", flush=True)
            except Exception as recv_err:
                print(f"Receive error: {recv_err}", flush=True)
                break

            message = json.loads(data)
            event = message.get("event")
            print(f"Event: {event}", flush=True)

            if event == "start":
                # Extract from nested "start" object
                start_data = message.get("start", {})
                stream_id = start_data.get("streamId") or message.get("streamId")
                call_id = start_data.get("callId") or message.get("callId")
                print(f"Stream started: {stream_id}", flush=True)
                print(f"Call ID: {call_id}", flush=True)

                # Send initial greeting
                greeting = "Hello! I'm your AI assistant. How can I help you today?"
                print(f"AI: {greeting}", flush=True)

                # Generate greeting audio with ElevenLabs (mulaw format for Plivo)
                tts_url = "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM"
                headers = {
                    "Accept": "audio/mpeg",
                    "Content-Type": "application/json",
                    "xi-api-key": ELEVENLABS_API_KEY
                }
                tts_data = {
                    "text": greeting,
                    "model_id": "eleven_turbo_v2_5",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
                }

                async with httpx.AsyncClient() as client:
                    response = await client.post(tts_url, json=tts_data, headers=headers, timeout=30)
                    if response.status_code == 200:
                        print("Greeting audio generated, sending to caller...", flush=True)
                        # Note: Plivo expects mulaw 8kHz. ElevenLabs returns MP3.
                        # For full audio playback, we'd need audio conversion (ffmpeg/pydub)
                        # For now, we'll skip sending and just acknowledge receipt
                        # TODO: Add proper MP3 to mulaw conversion
                    else:
                        print(f"TTS error: {response.status_code}", flush=True)

            elif event == "media":
                import time
                media = message.get("media", {})
                payload = media.get("payload", "")

                if payload:
                    # Decode base64 audio
                    audio_chunk = base64.b64decode(payload)
                    current_time = time.time()

                    # Calculate audio energy for VAD
                    energy = calculate_audio_energy(audio_chunk)

                    # --- INTERRUPTION DETECTION ---
                    # If AI is speaking and user starts talking, interrupt
                    if is_speaking and energy > ENERGY_THRESHOLD:
                        print(f"USER INTERRUPTION DETECTED! Energy: {energy:.0f}", flush=True)
                        is_interrupted = True
                        # Don't process yet, just flag the interruption
                        continue

                    # Skip if AI just finished speaking (give a small pause)
                    if current_time - last_response_time < MIN_PAUSE_AFTER_SPEECH:
                        if energy < ENERGY_THRESHOLD:  # Only skip if silence
                            audio_buffer.clear()
                            continue

                    # --- VAD: Speech Detection ---
                    if energy > ENERGY_THRESHOLD:
                        # User is speaking
                        if not user_is_speaking:
                            user_is_speaking = True
                            speech_start_time = current_time
                            print(f"Speech started (energy: {energy:.0f})", flush=True)
                        last_audio_time = current_time
                        audio_buffer.extend(audio_chunk)
                    else:
                        # Silence detected
                        if user_is_speaking:
                            # User was speaking, now silent - track silence duration
                            if last_silence_time == 0:
                                last_silence_time = current_time

                            silence_duration = current_time - last_silence_time

                            # Still buffer a bit of silence for context
                            if silence_duration < 0.3:
                                audio_buffer.extend(audio_chunk)

                    # --- PROCESS DECISION ---
                    # Process when: user spoke AND now silent for SILENCE_DURATION_TO_PROCESS
                    has_speech = len(audio_buffer) >= MIN_AUDIO_LENGTH
                    silence_duration = current_time - last_audio_time if last_audio_time > 0 else 0
                    should_process = (
                        has_speech and
                        user_is_speaking and
                        silence_duration >= SILENCE_DURATION_TO_PROCESS
                    )

                    # Also process if buffer gets too large (10 seconds max)
                    buffer_too_large = len(audio_buffer) >= 80000

                    if should_process or buffer_too_large:
                        if buffer_too_large:
                            print(f"Buffer full, processing {len(audio_buffer)} bytes...", flush=True)
                        else:
                            print(f"Silence detected ({silence_duration:.1f}s), processing {len(audio_buffer)} bytes...", flush=True)

                        # Reset VAD state
                        user_is_speaking = False
                        last_silence_time = 0

                        # Convert mulaw to PCM WAV for Whisper
                        pcm_samples = [mulaw_decode(b) for b in audio_buffer]
                        audio_buffer.clear()

                        # Create WAV in memory
                        wav_buffer = io.BytesIO()
                        with wave.open(wav_buffer, 'wb') as wav:
                            wav.setnchannels(1)
                            wav.setsampwidth(2)
                            wav.setframerate(8000)
                            wav.writeframes(struct.pack(f'<{len(pcm_samples)}h', *pcm_samples))

                        wav_buffer.seek(0)

                        # Transcribe with Whisper
                        try:
                            print("Sending to Whisper...", flush=True)
                            openai_client = OpenAI(api_key=OPENAI_API_KEY)

                            wav_content = wav_buffer.read()
                            print(f"WAV size: {len(wav_content)} bytes", flush=True)

                            transcript = openai_client.audio.transcriptions.create(
                                model="whisper-1",
                                file=("audio.wav", wav_content, "audio/wav"),
                                response_format="text",
                                prompt="This is a phone conversation. The caller may have background noise. Listen carefully for their words.",
                                language="en"  # Helps with accuracy
                            )

                            print(f"Whisper result: '{transcript}'", flush=True)

                            # Filter out noise/garbage transcriptions
                            clean_transcript = transcript.strip().lower()
                            garbage_words = ["you", "you.", "yeah", "hmm", "uh", "um", ""]
                            is_garbage = clean_transcript in garbage_words or len(clean_transcript) < 3

                            # Check for exit phrases (keyword matching as backup)
                            # But NOT if it's just a simple acknowledgment like "thank you"
                            is_simple_ack = clean_transcript in NOT_EXIT_PHRASES
                            is_exit = any(phrase in clean_transcript for phrase in EXIT_PHRASES) and not is_simple_ack

                            # --- Handle pending goodbye state ---
                            if pending_goodbye:
                                print(f"[GOODBYE FLOW] User response: '{clean_transcript}'", flush=True)

                                # Check if user said "no" or asked a follow-up question
                                # Strip punctuation for matching
                                clean_for_no_check = clean_transcript.strip('.,!?')
                                is_no_response = any(
                                    no_word == clean_for_no_check or
                                    clean_for_no_check.startswith(no_word + " ") or
                                    clean_for_no_check.endswith(" " + no_word)
                                    for no_word in NO_RESPONSES
                                )

                                print(f"[GOODBYE FLOW] is_no_response={is_no_response}, is_garbage={is_garbage}", flush=True)

                                if is_no_response or is_garbage:
                                    # User said no or silence - proceed with goodbye
                                    print(f"User confirmed goodbye: '{transcript}'", flush=True)
                                    goodbye_msg = "Thank you for calling! Goodbye and have a great day!"
                                    print(f"AI: {goodbye_msg}", flush=True)

                                    tts_url = "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM"
                                    tts_headers = {"Accept": "audio/mpeg", "Content-Type": "application/json", "xi-api-key": ELEVENLABS_API_KEY}

                                    try:
                                        async with httpx.AsyncClient() as http_client:
                                            tts_resp = await http_client.post(tts_url, json={
                                                "text": goodbye_msg, "model_id": "eleven_turbo_v2_5",
                                                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
                                            }, headers=tts_headers, timeout=30)
                                            if tts_resp.status_code == 200:
                                                from pydub import AudioSegment
                                                audio_seg = AudioSegment.from_mp3(io.BytesIO(tts_resp.content))
                                                audio_seg = audio_seg.set_frame_rate(8000).set_channels(1)
                                                mulaw_buf = io.BytesIO()
                                                audio_seg.export(mulaw_buf, format="wav", codec="pcm_mulaw")
                                                mulaw_buf.seek(44)
                                                mulaw_data = mulaw_buf.read()  # Read all data first
                                                for i in range(0, len(mulaw_data), 640):
                                                    chunk = mulaw_data[i:i+640]
                                                    if chunk:
                                                        await websocket.send_text(json.dumps({
                                                            "event": "playAudio",
                                                            "media": {"contentType": "audio/x-mulaw", "sampleRate": 8000,
                                                                      "payload": base64.b64encode(chunk).decode("utf-8")}
                                                        }))
                                                        await asyncio.sleep(0.04)
                                    except Exception as e:
                                        print(f"Error sending goodbye audio: {e}", flush=True)

                                    print("Ending call...", flush=True)
                                    await websocket.close()
                                    return
                                else:
                                    # User has a follow-up question! Cancel goodbye, answer question
                                    print(f"User has follow-up question: '{transcript}'", flush=True)
                                    pending_goodbye = False
                                    # Fall through to normal processing below

                            # --- Check for exit intent (only if not already in goodbye flow) ---
                            if is_exit and not pending_goodbye:
                                print(f"User: {transcript} [EXIT DETECTED]", flush=True)
                                pending_goodbye = True

                                # Ask if they have any other questions
                                ask_msg = "Before I let you go, do you have any other questions?"
                                print(f"AI: {ask_msg}", flush=True)

                                tts_url = "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM"
                                tts_headers = {"Accept": "audio/mpeg", "Content-Type": "application/json", "xi-api-key": ELEVENLABS_API_KEY}

                                async with httpx.AsyncClient() as http_client:
                                    tts_resp = await http_client.post(tts_url, json={
                                        "text": ask_msg, "model_id": "eleven_turbo_v2_5",
                                        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
                                    }, headers=tts_headers, timeout=30)
                                    if tts_resp.status_code == 200:
                                        from pydub import AudioSegment
                                        audio_seg = AudioSegment.from_mp3(io.BytesIO(tts_resp.content))
                                        audio_seg = audio_seg.set_frame_rate(8000).set_channels(1)
                                        mulaw_buf = io.BytesIO()
                                        audio_seg.export(mulaw_buf, format="wav", codec="pcm_mulaw")
                                        mulaw_buf.seek(44)
                                        mulaw_data = mulaw_buf.read()

                                        is_speaking = True
                                        audio_buffer.clear()
                                        for i in range(0, len(mulaw_data), 640):
                                            chunk = mulaw_data[i:i + 640]
                                            await websocket.send_text(json.dumps({
                                                "event": "playAudio",
                                                "media": {"contentType": "audio/x-mulaw", "sampleRate": 8000,
                                                          "payload": base64.b64encode(chunk).decode("utf-8")}
                                            }))
                                            await asyncio.sleep(0.04)
                                        is_speaking = False
                                        last_response_time = time.time()
                                        audio_buffer.clear()

                                print("Waiting for user's response to 'any other questions'...", flush=True)
                                continue  # Go back to listening

                            elif transcript.strip() and not is_garbage:
                                print(f"User: {transcript}", flush=True)

                                # Get AI response with function calling
                                conversation.append({"role": "user", "content": transcript})
                                print("Getting AI response...", flush=True)

                                ai_response_obj = openai_client.chat.completions.create(
                                    model="gpt-4o-mini",
                                    messages=conversation,
                                    tools=TOOLS,
                                    tool_choice="auto"
                                )

                                assistant_message = ai_response_obj.choices[0].message

                                # Check if AI wants to call a function
                                if assistant_message.tool_calls:
                                    print(f"Function call requested: {assistant_message.tool_calls[0].function.name}", flush=True)

                                    # Add assistant's message to conversation
                                    conversation.append(assistant_message)

                                    # Process each function call
                                    for tool_call in assistant_message.tool_calls:
                                        function_name = tool_call.function.name
                                        function_args = json.loads(tool_call.function.arguments)

                                        print(f"  → Calling {function_name}({function_args})", flush=True)

                                        # Execute the function
                                        function_result = execute_function(function_name, function_args)
                                        print(f"  → Result: {function_result[:100]}...", flush=True)

                                        # Add function result to conversation
                                        conversation.append({
                                            "role": "tool",
                                            "tool_call_id": tool_call.id,
                                            "content": function_result
                                        })

                                    # Get final response with function results
                                    final_response = openai_client.chat.completions.create(
                                        model="gpt-4o-mini",
                                        messages=conversation
                                    )
                                    ai_response = final_response.choices[0].message.content
                                else:
                                    # No function call, direct response
                                    ai_response = assistant_message.content

                                print(f"AI: {ai_response}", flush=True)

                                # Check if LLM detected exit intent
                                # BUT ignore it if user just said a simple acknowledgment like "thank you"
                                is_simple_acknowledgment = clean_transcript in NOT_EXIT_PHRASES

                                # If LLM included [EXIT_INTENT_DETECTED] but it's just an acknowledgment, strip it
                                if "[EXIT_INTENT_DETECTED]" in ai_response and is_simple_acknowledgment:
                                    print(f"Ignoring exit detection for acknowledgment: '{clean_transcript}'", flush=True)
                                    ai_response = ai_response.replace("[EXIT_INTENT_DETECTED]", "").strip()

                                if "[EXIT_INTENT_DETECTED]" in ai_response and not is_simple_acknowledgment:
                                    print("LLM detected exit intent!", flush=True)
                                    pending_goodbye = True

                                    # Ask if they have other questions
                                    goodbye_sequence_msg = "Before I let you go, do you have any other questions?"
                                    print(f"AI: {goodbye_sequence_msg}", flush=True)

                                    tts_url = "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM"
                                    tts_headers = {"Accept": "audio/mpeg", "Content-Type": "application/json", "xi-api-key": ELEVENLABS_API_KEY}

                                    async with httpx.AsyncClient() as http_client:
                                        tts_resp = await http_client.post(tts_url, json={
                                            "text": goodbye_sequence_msg, "model_id": "eleven_turbo_v2_5",
                                            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
                                        }, headers=tts_headers, timeout=30)
                                        if tts_resp.status_code == 200:
                                            from pydub import AudioSegment
                                            audio_seg = AudioSegment.from_mp3(io.BytesIO(tts_resp.content))
                                            audio_seg = audio_seg.set_frame_rate(8000).set_channels(1)
                                            mulaw_buf = io.BytesIO()
                                            audio_seg.export(mulaw_buf, format="wav", codec="pcm_mulaw")
                                            mulaw_buf.seek(44)
                                            mulaw_data = mulaw_buf.read()
                                            is_speaking = True
                                            audio_buffer.clear()
                                            for i in range(0, len(mulaw_data), 640):
                                                chunk = mulaw_data[i:i + 640]
                                                await websocket.send_text(json.dumps({
                                                    "event": "playAudio",
                                                    "media": {"contentType": "audio/x-mulaw", "sampleRate": 8000,
                                                              "payload": base64.b64encode(chunk).decode("utf-8")}
                                                }))
                                                await asyncio.sleep(0.04)
                                            is_speaking = False
                                            last_response_time = time.time()
                                            audio_buffer.clear()

                                    print("Waiting for user's response (LLM exit)...", flush=True)
                                    continue  # Go back to listening for user response

                                conversation.append({"role": "assistant", "content": ai_response})

                                # Generate and send TTS audio
                                print("Generating TTS audio...", flush=True)
                                tts_url = "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM"
                                tts_headers = {
                                    "Accept": "audio/mpeg",
                                    "Content-Type": "application/json",
                                    "xi-api-key": ELEVENLABS_API_KEY
                                }
                                tts_payload = {
                                    "text": ai_response,
                                    "model_id": "eleven_turbo_v2_5",
                                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
                                }

                                async with httpx.AsyncClient() as http_client:
                                    tts_response = await http_client.post(tts_url, json=tts_payload, headers=tts_headers, timeout=30)
                                    if tts_response.status_code == 200:
                                        mp3_audio = tts_response.content
                                        print(f"TTS audio: {len(mp3_audio)} bytes MP3", flush=True)

                                        # Convert MP3 to mulaw using pydub
                                        try:
                                            from pydub import AudioSegment

                                            # Load MP3
                                            audio_segment = AudioSegment.from_mp3(io.BytesIO(mp3_audio))

                                            # Convert to 8kHz mono
                                            audio_segment = audio_segment.set_frame_rate(8000).set_channels(1)

                                            # Export as raw mulaw
                                            mulaw_buffer = io.BytesIO()
                                            audio_segment.export(mulaw_buffer, format="wav", codec="pcm_mulaw")
                                            mulaw_buffer.seek(44)  # Skip WAV header
                                            mulaw_audio = mulaw_buffer.read()

                                            print(f"Mulaw audio: {len(mulaw_audio)} bytes", flush=True)

                                            # Mark as speaking and clear buffer
                                            is_speaking = True
                                            audio_buffer.clear()

                                            # Send audio chunks to Plivo (with interruption check)
                                            chunk_size = 640  # ~80ms at 8kHz
                                            total_chunks = len(mulaw_audio) // chunk_size
                                            print(f"Sending {total_chunks} audio chunks...", flush=True)

                                            is_interrupted = False  # Reset interruption flag
                                            chunks_sent = 0

                                            for i in range(0, len(mulaw_audio), chunk_size):
                                                # Check for interruption
                                                if is_interrupted:
                                                    print(f"Interrupted after {chunks_sent}/{total_chunks} chunks!", flush=True)
                                                    break

                                                chunk = mulaw_audio[i:i + chunk_size]
                                                play_message = {
                                                    "event": "playAudio",
                                                    "media": {
                                                        "contentType": "audio/x-mulaw",
                                                        "sampleRate": 8000,
                                                        "payload": base64.b64encode(chunk).decode("utf-8")
                                                    }
                                                }
                                                await websocket.send_text(json.dumps(play_message))
                                                chunks_sent += 1
                                                await asyncio.sleep(0.04)  # Pace the audio

                                            # Done speaking - update timestamp and flag
                                            is_speaking = False
                                            last_response_time = time.time()
                                            audio_buffer.clear()  # Clear any audio received during playback

                                            if is_interrupted:
                                                print("AI was interrupted, ready to listen...", flush=True)
                                                is_interrupted = False
                                                user_is_speaking = True  # User is likely still talking
                                            else:
                                                print("Audio sent! Waiting for user...", flush=True)

                                        except Exception as conv_err:
                                            print(f"Audio conversion error: {conv_err}", flush=True)
                                    else:
                                        print(f"TTS error: {tts_response.status_code}", flush=True)

                                # Keep conversation manageable
                                if len(conversation) > 12:
                                    conversation = conversation[:1] + conversation[-10:]
                            elif is_garbage:
                                print(f"Filtered noise: '{transcript}'", flush=True)
                            else:
                                print("No speech detected in audio", flush=True)

                        except Exception as e:
                            import traceback
                            print(f"Transcription error: {e}", flush=True)
                            print(traceback.format_exc(), flush=True)

            elif event == "stop":
                print(f"Stream stopped: {stream_id}")
                break

            elif event == "dtmf":
                digit = message.get("digit")
                print(f"DTMF: {digit}")

    except Exception as e:
        print(f"WebSocket error: {e}")

    print("Call ended")


# ============ Plivo XML Endpoints ============

@app.get("/")
def health():
    """Health check."""
    return {"status": "ok", "service": "Pipecat IVR"}


@app.post("/voice/incoming")
async def incoming_call(request: Request):
    """
    IVR entry point with AI option.
    """
    host = request.headers.get("host", "localhost:8000")
    protocol = "https" if "ngrok" in host else "http"
    base_url = f"{protocol}://{host}"

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak>Welcome to our AI-powered service.</Speak>
    <GetDigits action="{base_url}/voice/menu" method="POST" timeout="10" numDigits="1">
        <Speak>Press 1 for Sales. Press 2 for Support. Press 3 to speak with our AI assistant.</Speak>
    </GetDigits>
    <Speak>We didn't receive any input. Goodbye.</Speak>
</Response>"""

    return Response(content=xml, media_type="application/xml")


@app.post("/voice/menu")
async def menu_handler(request: Request):
    """
    Menu handler - routes to AI on option 3.
    """
    form_data = await request.form()
    digits = form_data.get("Digits", "")

    host = request.headers.get("host", "localhost:8000")
    protocol = "https" if "ngrok" in host else "http"
    base_url = f"{protocol}://{host}"
    ws_protocol = "wss" if "ngrok" in host else "ws"
    ws_url = f"{ws_protocol}://{host}/ws/audio"

    if digits == "1":
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak>Connecting you to Sales. Please hold.</Speak>
</Response>"""

    elif digits == "2":
        xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak>Connecting you to Support. Please hold.</Speak>
</Response>"""

    elif digits == "3":
        # Connect to AI assistant via WebSocket
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak>Connecting you to our AI assistant. You can start speaking after the beep.</Speak>
    <Stream streamTimeout="3600" keepCallAlive="true" bidirectional="true" contentType="audio/x-mulaw;rate=8000">
        {ws_url}
    </Stream>
</Response>"""

    else:
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak>Invalid option.</Speak>
    <GetDigits action="{base_url}/voice/menu" method="POST" timeout="10" numDigits="1">
        <Speak>Press 1 for Sales. Press 2 for Support. Press 3 for AI assistant.</Speak>
    </GetDigits>
</Response>"""

    return Response(content=xml, media_type="application/xml")


@app.post("/voice/ai-direct")
async def ai_direct(request: Request):
    """
    Direct connection to AI (bypasses menu).
    """
    host = request.headers.get("host", "localhost:8000")
    ws_protocol = "wss" if "ngrok" in host else "ws"
    ws_url = f"{ws_protocol}://{host}/ws/audio"

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak>Connecting you to our AI assistant.</Speak>
    <Stream streamTimeout="3600" keepCallAlive="true" bidirectional="true" contentType="audio/x-mulaw;rate=8000">
        {ws_url}
    </Stream>
</Response>"""

    return Response(content=xml, media_type="application/xml")


# ============ Entry Point ============

if __name__ == "__main__":
    print("\n" + "="*60)
    print("PIPECAT IVR INTEGRATION")
    print("="*60)

    print(f"\nAPI Keys:")
    print(f"  OPENAI_API_KEY:     {'Found' if OPENAI_API_KEY else 'MISSING'}")
    print(f"  ELEVENLABS_API_KEY: {'Found' if ELEVENLABS_API_KEY else 'MISSING'}")
    print(f"  PLIVO_AUTH_ID:      {'Found' if PLIVO_AUTH_ID else 'MISSING'}")
    print(f"  PLIVO_AUTH_TOKEN:   {'Found' if PLIVO_AUTH_TOKEN else 'MISSING'}")

    if not all([OPENAI_API_KEY, ELEVENLABS_API_KEY, PLIVO_AUTH_ID, PLIVO_AUTH_TOKEN]):
        print("\nMissing required API keys!")
        exit(1)

    print(f"\nEndpoints:")
    print(f"  GET  /                  - Health check")
    print(f"  POST /voice/incoming    - IVR entry (has AI option)")
    print(f"  POST /voice/menu        - Menu handler")
    print(f"  POST /voice/ai-direct   - Direct AI connection")
    print(f"  WS   /ws/audio          - Audio streaming")

    print(f"\nTo test:")
    print(f"  1. Start server:  python3.11 pipecat_ivr.py")
    print(f"  2. Start ngrok:   ngrok http 8000")
    print(f"  3. Update Plivo webhook to: <ngrok-url>/voice/incoming")
    print(f"  4. Call your Plivo number, press 3 for AI")

    print("\n" + "="*60)
    print("Starting server on http://localhost:8000")
    print("="*60 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8000)
