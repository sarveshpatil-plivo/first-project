"""
LiveKit Voice Agent - Updated API
Run: python3.11 minimal_agent.py dev
"""

import os
from dotenv import load_dotenv
load_dotenv()

from livekit import agents
from livekit.agents import AgentSession, Agent, cli
from livekit.plugins import deepgram, openai, silero

class Assistant(Agent):
    def __init__(self):
        super().__init__(
            instructions="You are a helpful voice AI assistant. Keep responses brief and natural."
        )

async def entrypoint(ctx: agents.JobContext):
    await ctx.connect(auto_subscribe="audio_only")

    print("Connected to room, starting session...", flush=True)

    session = AgentSession(
        stt=deepgram.STT(model="nova-2", language="en"),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=openai.TTS(voice="nova"),
        vad=silero.VAD.load(),
    )

    await session.start(
        room=ctx.room,
        agent=Assistant(),
    )

    print("Session started, greeting user...", flush=True)

    # Greet the user
    await session.generate_reply(
        instructions="Greet the user and offer your assistance."
    )

    print("Greeting sent!", flush=True)

if __name__ == "__main__":
    print("\nLIVEKIT VOICE AGENT")
    print("=" * 40)

    cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="voice-assistant",
        )
    )
