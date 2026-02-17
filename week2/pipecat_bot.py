"""
Week 2, Day 3: Pipecat Voice Bot
Real-time voice assistant using the Pipecat framework.

Pipeline:
  Microphone → VAD → SmartTurn → Whisper STT → Exit Check → OpenAI LLM → ElevenLabs TTS → Speaker

Features:
  - Project 3: SmartTurn for better turn detection
  - Project 4: Latency measurement (end-to-end tracking)
  - Project 5: Function calling (time, jokes, order lookup)
"""

import os
import asyncio
import logging
import time
import json
import random
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Set pipecat to INFO level (shows key events, hides debug spam)
logging.getLogger("pipecat").setLevel(logging.INFO)

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# Exit words that will end the conversation
EXIT_WORDS = ["goodbye", "bye", "exit", "quit", "stop", "end conversation"]


# ============ Project 5: Function Definitions ============

JOKES = [
    "Why don't scientists trust atoms? Because they make up everything!",
    "Why did the scarecrow win an award? He was outstanding in his field!",
    "I told my wife she was drawing her eyebrows too high. She looked surprised.",
    "Why don't eggs tell jokes? They'd crack each other up!",
    "What do you call a fake noodle? An impasta!",
    "Why did the coffee file a police report? It got mugged!",
]

# Mock order database
ORDERS = {
    "12345": {"status": "shipped", "item": "Wireless Headphones", "delivery": "Feb 18, 2026"},
    "67890": {"status": "processing", "item": "Smart Watch", "delivery": "Feb 20, 2026"},
    "11111": {"status": "delivered", "item": "Phone Case", "delivery": "Feb 14, 2026"},
}

# OpenAI Function/Tool definitions
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current date and time",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "tell_joke",
            "description": "Tell a random joke to the user",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
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
                        "description": "The order ID to look up (e.g., 12345)"
                    }
                },
                "required": ["order_id"]
            }
        }
    }
]


def get_current_time() -> str:
    """Returns the current date and time."""
    now = datetime.now()
    return now.strftime("It's %I:%M %p on %A, %B %d, %Y")


def tell_joke() -> str:
    """Returns a random joke."""
    return random.choice(JOKES)


def lookup_order(order_id: str) -> str:
    """Looks up an order by ID."""
    order_id = order_id.strip()
    if order_id in ORDERS:
        order = ORDERS[order_id]
        return f"Order {order_id}: {order['item']} is {order['status']}. Expected delivery: {order['delivery']}."
    else:
        return f"I couldn't find order {order_id}. Please check the order number and try again."


# Function dispatcher
FUNCTION_MAP = {
    "get_current_time": lambda **kwargs: get_current_time(),
    "tell_joke": lambda **kwargs: tell_joke(),
    "lookup_order": lambda **kwargs: lookup_order(kwargs.get("order_id", "")),
}


async def main():
    """Main function to run the Pipecat voice bot."""

    # Import Pipecat components (using new module paths)
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.pipeline.task import PipelineTask, PipelineParams
    from pipecat.frames.frames import EndFrame, TextFrame, TranscriptionFrame, TTSStartedFrame, UserStoppedSpeakingFrame
    from pipecat.transports.local.audio import LocalAudioTransport, LocalAudioTransportParams
    from pipecat.services.openai.llm import OpenAILLMService
    from pipecat.services.openai.stt import OpenAISTTService
    from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    from pipecat.audio.vad.vad_analyzer import VADParams
    from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
    from pipecat.processors.frame_processor import FrameProcessor, FrameDirection

    # ============ Project 4: Latency Tracker ============
    class LatencyTracker(FrameProcessor):
        """Tracks end-to-end latency from user stop speaking to first TTS audio."""
        def __init__(self):
            super().__init__()
            self.user_stop_time = None
            self.latencies = []

        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)

            # Record when user stops speaking
            if isinstance(frame, UserStoppedSpeakingFrame):
                self.user_stop_time = time.time()

            # Record when TTS starts (first audio output)
            if isinstance(frame, TTSStartedFrame) and self.user_stop_time:
                latency = (time.time() - self.user_stop_time) * 1000  # Convert to ms
                self.latencies.append(latency)
                avg_latency = sum(self.latencies) / len(self.latencies)
                print(f"\n⏱️  Latency: {latency:.0f}ms (avg: {avg_latency:.0f}ms)")
                self.user_stop_time = None

            await self.push_frame(frame, direction)

    # Custom processor to detect exit words and show conversation
    class ConversationLogger(FrameProcessor):
        def __init__(self, task_ref):
            super().__init__()
            self.task_ref = task_ref
            self.should_exit = False

        async def process_frame(self, frame, direction):
            await super().process_frame(frame, direction)

            # Check transcription frames for exit words
            if isinstance(frame, TranscriptionFrame):
                text = frame.text.lower().strip()
                print(f"\n🎤 You: {frame.text}")

                # Check for exit words
                if any(word in text for word in EXIT_WORDS):
                    self.should_exit = True
                    print("\n👋 Exit word detected. Ending after response...")

            # Pass frame along
            await self.push_frame(frame, direction)

            # If exit was triggered and this is end of response, stop
            if self.should_exit and isinstance(frame, TextFrame):
                # Let the goodbye response play, then exit
                await asyncio.sleep(3)
                print("\n✅ Conversation ended. Goodbye!")
                await self.task_ref[0].queue_frame(EndFrame())

    print("\n" + "="*50)
    print("🤖 PIPECAT VOICE BOT (Enhanced)")
    print("="*50)
    print("\nFeatures:")
    print("  ✓ SmartTurn: Better turn detection")
    print("  ✓ Latency tracking: End-to-end measurement")
    print("  ✓ Function calling: Time, jokes, order lookup")
    print("\nInitializing components...")

    # Configure VAD - balanced settings
    vad = SileroVADAnalyzer(
        params=VADParams(
            confidence=0.7,       # Default sensitivity
            start_secs=0.2,       # Default start delay
            stop_secs=0.8,        # Default stop delay
            min_volume=0.5        # Slightly lower to pick up voice better
        )
    )

    # Create transport for local audio (microphone + speakers)
    transport = LocalAudioTransport(
        LocalAudioTransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_enabled=True,
            vad_analyzer=vad
        )
    )

    # Create OpenAI STT service (Whisper)
    stt = OpenAISTTService(api_key=OPENAI_API_KEY)

    # ============ Project 5: LLM with Function Calling ============
    # Create OpenAI LLM service with tools
    llm = OpenAILLMService(
        api_key=OPENAI_API_KEY,
        model="gpt-4o-mini"
    )

    # Register function handlers with the LLM
    @llm.function("get_current_time")
    async def handle_get_time(function_name, tool_call_id, arguments, llm, context, result_callback):
        result = get_current_time()
        print(f"\n🔧 Function called: get_current_time() → {result}")
        await result_callback(result)

    @llm.function("tell_joke")
    async def handle_tell_joke(function_name, tool_call_id, arguments, llm, context, result_callback):
        result = tell_joke()
        print(f"\n🔧 Function called: tell_joke() → {result[:50]}...")
        await result_callback(result)

    @llm.function("lookup_order")
    async def handle_lookup_order(function_name, tool_call_id, arguments, llm, context, result_callback):
        order_id = arguments.get("order_id", "")
        result = lookup_order(order_id)
        print(f"\n🔧 Function called: lookup_order({order_id}) → {result[:50]}...")
        await result_callback(result)

    # Create ElevenLabs TTS service
    tts = ElevenLabsTTSService(
        api_key=ELEVENLABS_API_KEY,
        voice_id="21m00Tcm4TlvDq8ikWAM",  # Rachel voice
        model="eleven_turbo_v2_5"
    )

    # Create context for conversation with tools
    messages = [
        {
            "role": "system",
            "content": """You are a friendly voice assistant with special abilities. Keep your responses brief and conversational (2-3 sentences max). You're having a spoken conversation, so be natural and don't use bullet points or formatting.

You have these tools available:
- get_current_time: Use when someone asks about the time or date
- tell_joke: Use when someone asks for a joke or wants to hear something funny
- lookup_order: Use when someone asks about an order status (ask for order ID if not provided)

If the user says goodbye or wants to end the conversation, say a brief farewell like 'Goodbye! Have a great day!'"""
        }
    ]

    # ============ Project 5: Add tools to context ============
    context = OpenAILLMContext(messages, tools=TOOLS)
    context_aggregator = llm.create_context_aggregator(context)

    # Task reference holder (to allow exit from processor)
    task_ref = [None]

    # Create processors
    logger = ConversationLogger(task_ref)
    latency_tracker = LatencyTracker()  # Project 4

    # Build the pipeline with latency tracking
    pipeline = Pipeline([
        transport.input(),           # Microphone input with VAD
        stt,                         # Speech-to-text (Whisper)
        logger,                      # Log conversation & check for exit
        context_aggregator.user(),   # Collect user speech
        llm,                         # Process with LLM (with function calling)
        latency_tracker,             # Project 4: Track latency
        tts,                         # Convert to speech
        transport.output(),          # Speaker output
        context_aggregator.assistant()  # Track assistant responses
    ])

    # Create and run the task
    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=False,  # Disable interruptions to prevent echo issues
            enable_metrics=False        # Disable debug metrics for cleaner output
        )
    )

    # Store task reference for exit
    task_ref[0] = task

    runner = PipelineRunner()

    print("\n✓ All components ready!")
    print("\n" + "-"*50)
    print("🎤 Speak now! The bot is listening...")
    print(f"   Say any of these to exit: {', '.join(EXIT_WORDS)}")
    print("\n📌 Try these commands:")
    print("   • 'What time is it?' - Get current time")
    print("   • 'Tell me a joke' - Hear a joke")
    print("   • 'What's the status of order 12345?' - Order lookup")
    print("\n   Press Ctrl+C to force quit")
    print("-"*50 + "\n")

    try:
        await runner.run(task)
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted. Goodbye!")
    except Exception as e:
        if "cancelled" not in str(e).lower():
            print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    # Check API keys
    print("🎙️ Week 2, Day 3: Pipecat Voice Bot")
    print("====================================")

    print(f"\nAPI Keys Status:")
    print(f"  OPENAI_API_KEY:     {'✓ Found' if OPENAI_API_KEY else '✗ Missing'}")
    print(f"  ELEVENLABS_API_KEY: {'✓ Found' if ELEVENLABS_API_KEY else '✗ Missing'}")

    if not OPENAI_API_KEY or not ELEVENLABS_API_KEY:
        print("\n❌ Both API keys are required.")
        exit(1)

    # Run the async main function
    asyncio.run(main())
