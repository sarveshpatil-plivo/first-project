"""
Week 2, Day 3: Pipecat Voice Bot
Real-time voice assistant using the Pipecat framework.

Pipeline:
  Microphone → VAD → Whisper STT → Exit Check → OpenAI LLM → ElevenLabs TTS → Speaker
"""

import os
import asyncio
import logging
from dotenv import load_dotenv

load_dotenv()

# Set pipecat to INFO level (shows key events, hides debug spam)
logging.getLogger("pipecat").setLevel(logging.INFO)

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# Exit words that will end the conversation
EXIT_WORDS = ["goodbye", "bye", "exit", "quit", "stop", "end conversation"]


async def main():
    """Main function to run the Pipecat voice bot."""

    # Import Pipecat components (using new module paths)
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.pipeline.task import PipelineTask, PipelineParams
    from pipecat.frames.frames import EndFrame, TextFrame, TranscriptionFrame
    from pipecat.transports.local.audio import LocalAudioTransport, LocalAudioTransportParams
    from pipecat.services.openai.llm import OpenAILLMService
    from pipecat.services.openai.stt import OpenAISTTService
    from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    from pipecat.audio.vad.vad_analyzer import VADParams
    from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
    from pipecat.processors.frame_processor import FrameProcessor, FrameDirection

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
    print("🤖 PIPECAT VOICE BOT")
    print("="*50)
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

    # Create OpenAI LLM service
    llm = OpenAILLMService(
        api_key=OPENAI_API_KEY,
        model="gpt-4o-mini"
    )

    # Create ElevenLabs TTS service
    tts = ElevenLabsTTSService(
        api_key=ELEVENLABS_API_KEY,
        voice_id="21m00Tcm4TlvDq8ikWAM",  # Rachel voice
        model="eleven_turbo_v2_5"
    )

    # Create context for conversation
    messages = [
        {
            "role": "system",
            "content": """You are a friendly voice assistant. Keep your responses brief and conversational
(2-3 sentences max). You're having a spoken conversation, so be natural and don't use
bullet points or formatting. If the user says goodbye or wants to end the conversation,
say a brief farewell like 'Goodbye! Have a great day!'"""
        }
    ]

    context = OpenAILLMContext(messages)
    context_aggregator = llm.create_context_aggregator(context)

    # Task reference holder (to allow exit from processor)
    task_ref = [None]

    # Create conversation logger
    logger = ConversationLogger(task_ref)

    # Build the pipeline
    pipeline = Pipeline([
        transport.input(),           # Microphone input with VAD
        stt,                         # Speech-to-text (Whisper)
        logger,                      # Log conversation & check for exit
        context_aggregator.user(),   # Collect user speech
        llm,                         # Process with LLM
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
    print("   Or press Ctrl+C to force quit")
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
