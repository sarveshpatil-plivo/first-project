"""
Simple Voice Test - Minimal Pipecat bot to verify pipeline works.
Run: python3.11 simple_voice_test.py
"""

import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

async def main():
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.pipeline.task import PipelineTask, PipelineParams
    from pipecat.transports.local.audio import LocalAudioTransport, LocalAudioTransportParams
    from pipecat.services.openai.llm import OpenAILLMService
    from pipecat.services.openai.stt import OpenAISTTService
    from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
    from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
    from pipecat.audio.vad.silero import SileroVADAnalyzer

    print("\n" + "="*50)
    print("SIMPLE VOICE TEST")
    print("="*50)
    print("\nSpeak into your microphone. Say 'goodbye' to exit.\n")

    # Audio transport (mic + speaker)
    transport = LocalAudioTransport(
        LocalAudioTransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
        )
    )

    # STT (Whisper)
    stt = OpenAISTTService(api_key=OPENAI_API_KEY)

    # LLM
    llm = OpenAILLMService(
        api_key=OPENAI_API_KEY,
        model="gpt-4o-mini"
    )

    # TTS (ElevenLabs)
    tts = ElevenLabsTTSService(
        api_key=ELEVENLABS_API_KEY,
        voice_id="21m00Tcm4TlvDq8ikWAM",  # Rachel
        model="eleven_turbo_v2_5"
    )

    # Conversation context
    messages = [
        {
            "role": "system",
            "content": "You are a friendly voice assistant. Keep responses brief (1-2 sentences). Be natural and conversational."
        }
    ]
    context = OpenAILLMContext(messages)
    context_aggregator = llm.create_context_aggregator(context)

    # Build pipeline
    pipeline = Pipeline([
        transport.input(),
        stt,
        context_aggregator.user(),
        llm,
        tts,
        transport.output(),
        context_aggregator.assistant()
    ])

    task = PipelineTask(
        pipeline,
        params=PipelineParams(allow_interruptions=True)
    )

    runner = PipelineRunner()

    print("Listening... (Ctrl+C to stop)\n")

    try:
        await runner.run(task)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    asyncio.run(main())
