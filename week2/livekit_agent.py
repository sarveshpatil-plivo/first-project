"""
Week 2, Day 5: LiveKit Voice Agent (Full Version)
AI voice agent with function calling, custom personality, and call logging.

Run: python3.11 livekit_agent.py dev
Test Browser: https://agents-playground.livekit.io/
Test Phone: Call your Plivo number (after SIP trunk setup)
"""

import os
import json
import logging
from datetime import datetime
from typing import Annotated
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not needed in production

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API Keys
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")
LIVEKIT_URL = os.getenv("LIVEKIT_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# Call log file
CALL_LOG_FILE = "call_logs.json"

from livekit.agents import (
    Agent,
    AgentSession,
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    RoomInputOptions,
    RunContext,
    cli,
    function_tool,
)
from livekit.plugins import deepgram, elevenlabs, openai, silero
from livekit.api import LiveKitAPI


# =============================================================================
# CALL LOGGING
# =============================================================================

def log_call(room_name: str, event: str, details: dict = None):
    """Log call events to JSON file."""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "room": room_name,
        "event": event,
        "details": details or {}
    }

    # Load existing logs
    logs = []
    if os.path.exists(CALL_LOG_FILE):
        try:
            with open(CALL_LOG_FILE, "r") as f:
                logs = json.load(f)
        except:
            logs = []

    # Append and save
    logs.append(log_entry)
    with open(CALL_LOG_FILE, "w") as f:
        json.dump(logs, f, indent=2)

    logger.info(f"Call log: {event} - {details}")


# =============================================================================
# FUNCTION TOOLS (AI can call these)
# =============================================================================

@function_tool
def check_order_status(
    order_id: Annotated[str, "The order ID to check (e.g., ORD-12345)"]
) -> str:
    """Check the status of a customer order."""
    # Simulated order database
    orders = {
        "ORD-12345": {"status": "shipped", "eta": "tomorrow", "item": "Blue Widget"},
        "ORD-67890": {"status": "processing", "eta": "3 days", "item": "Red Gadget"},
        "ORD-11111": {"status": "delivered", "eta": "completed", "item": "Green Thing"},
    }

    if order_id in orders:
        order = orders[order_id]
        return f"Order {order_id}: {order['item']} is {order['status']}. ETA: {order['eta']}"
    else:
        return f"Order {order_id} not found. Please verify the order number."


@function_tool
def get_business_hours() -> str:
    """Get current business hours and availability."""
    now = datetime.now()
    day = now.strftime("%A")
    hour = now.hour

    hours = {
        "Monday": "9 AM - 6 PM",
        "Tuesday": "9 AM - 6 PM",
        "Wednesday": "9 AM - 6 PM",
        "Thursday": "9 AM - 6 PM",
        "Friday": "9 AM - 5 PM",
        "Saturday": "10 AM - 2 PM",
        "Sunday": "Closed",
    }

    is_open = day != "Sunday" and 9 <= hour < 18
    status = "currently open" if is_open else "currently closed"

    return f"We are {status}. Today ({day}) hours: {hours.get(day, 'Unknown')}. Regular hours: Monday-Friday 9 AM - 6 PM, Saturday 10 AM - 2 PM."


@function_tool
def schedule_callback(
    phone_number: Annotated[str, "Customer phone number for callback"],
    preferred_time: Annotated[str, "Preferred callback time (e.g., 'tomorrow morning')"]
) -> str:
    """Schedule a callback from a human agent."""
    logger.info(f"Callback scheduled: {phone_number} at {preferred_time}")
    return f"I've scheduled a callback to {phone_number} for {preferred_time}. A team member will call you back. Is there anything else I can help with?"


@function_tool
def transfer_to_department(
    department: Annotated[str, "Department to transfer to: sales, support, or billing"]
) -> str:
    """Transfer the call to a specific department."""
    departments = {
        "sales": "Sales team - for new orders and pricing",
        "support": "Technical support - for product help",
        "billing": "Billing department - for invoices and payments",
    }

    if department.lower() in departments:
        logger.info(f"Transfer requested to: {department}")
        return f"Transferring you to {departments[department.lower()]}. Please hold..."
    else:
        return f"Available departments: sales, support, billing. Which would you like?"


@function_tool
def lookup_product(
    product_name: Annotated[str, "Product name or keyword to search"]
) -> str:
    """Look up product information and pricing."""
    products = {
        "widget": {"name": "Blue Widget", "price": "$29.99", "stock": "In stock"},
        "gadget": {"name": "Red Gadget", "price": "$49.99", "stock": "Low stock"},
        "thing": {"name": "Green Thing", "price": "$19.99", "stock": "In stock"},
        "premium": {"name": "Premium Bundle", "price": "$99.99", "stock": "In stock"},
    }

    # Simple search
    for key, product in products.items():
        if key in product_name.lower() or product_name.lower() in product["name"].lower():
            return f"{product['name']}: {product['price']} - {product['stock']}"

    return f"No product found matching '{product_name}'. We have: Widget, Gadget, Thing, and Premium Bundle."


@function_tool
async def end_call(
    ctx: RunContext,
    confirmed: Annotated[bool, "True if user confirmed they want to end the call"]
) -> str:
    """End the call after user confirms. Only call this when user explicitly confirms 'yes' to ending."""
    if not confirmed:
        return "User did not confirm. Continue the conversation."

    # Say goodbye
    ctx.session.say("Thank you for calling Acme Corporation. Have a great day! Goodbye.")

    # Get session reference and schedule close
    session = ctx.session

    import asyncio
    asyncio.create_task(_close_session(session))

    return "Goodbye message sent. Call ending."


async def _close_session(session):
    """Close the agent session after goodbye plays."""
    import asyncio
    await asyncio.sleep(4)

    try:
        await session.aclose()
    except Exception as e:
        logger.error(f"Session close error: {e}")


# =============================================================================
# AI RECEPTIONIST AGENT
# =============================================================================

class ReceptionistAgent(Agent):
    """AI Receptionist with function calling capabilities."""

    def __init__(self):
        super().__init__(
            instructions="""You are a friendly and professional AI receptionist for Acme Corporation.

PERSONALITY:
- Warm, helpful, and efficient
- Speak naturally and conversationally
- Keep responses brief (1-2 sentences unless more detail is needed)
- Be proactive in offering help

CAPABILITIES (use these tools when appropriate):
- check_order_status: When customer asks about their order
- get_business_hours: When asked about hours or availability
- schedule_callback: When customer wants a human to call back
- transfer_to_department: When customer needs sales, support, or billing
- lookup_product: When customer asks about products or prices
- end_call: When user wants to end/hangup the call (ONLY after confirmation)

ENDING CALLS - IMPORTANT:
When user indicates they want to end the call (says goodbye, "that's all", "I'm done", "hang up", etc.):
1. FIRST ask: "Is there anything else I can help you with before we end the call?"
2. If user says "no", "nothing", "that's it", "yes end it", "goodbye" - call end_call with confirmed=True
3. If user asks another question, help them (do NOT ask again about ending)
4. NEVER loop the confirmation question - ask ONCE, then either end or continue helping

GUIDELINES:
- Always greet callers warmly
- Ask clarifying questions if needed
- Offer to transfer to a human if the AI can't help

Remember: You're the first point of contact. Make a great impression!""",
            tools=[
                check_order_status,
                get_business_hours,
                schedule_callback,
                transfer_to_department,
                lookup_product,
                end_call,
            ],
        )

    async def on_enter(self):
        """Called when agent enters - send greeting."""
        self.session.say(
            "Hello! Thank you for calling Acme Corporation. "
            "I'm your AI assistant. How can I help you today?"
        )


# =============================================================================
# MAIN ENTRYPOINT
# =============================================================================

async def entrypoint(ctx: JobContext):
    """Main entry point for LiveKit agent."""
    room_name = ctx.room.name
    logger.info(f"Connecting to room: {room_name}")

    # Log call start
    log_call(room_name, "call_started", {"room": room_name})

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # Create session with all components
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(api_key=DEEPGRAM_API_KEY),
        llm=openai.LLM(api_key=OPENAI_API_KEY, model="gpt-4o-mini"),
        tts=elevenlabs.TTS(
            api_key=ELEVENLABS_API_KEY,
            voice_id="EXAVITQu4vr4xnSDxMaL",  # Sarah - Mature, Reassuring, Confident
            model="eleven_turbo_v2_5",
        ),
    )

    # Start the session with our receptionist agent
    await session.start(
        room=ctx.room,
        agent=ReceptionistAgent(),
        room_input_options=RoomInputOptions(),
    )

    logger.info("AI Receptionist running!")

    # Log that agent is active
    log_call(room_name, "agent_active", {"agent": "ReceptionistAgent"})


# =============================================================================
# CLI ENTRY
# =============================================================================

def main():
    print("\n" + "=" * 60)
    print("LIVEKIT AI RECEPTIONIST")
    print("=" * 60)

    keys_ok = all([
        LIVEKIT_API_KEY and "your-" not in LIVEKIT_API_KEY,
        LIVEKIT_API_SECRET and "your-" not in LIVEKIT_API_SECRET,
        LIVEKIT_URL and "your-" not in LIVEKIT_URL,
        OPENAI_API_KEY,
        DEEPGRAM_API_KEY and "your-" not in DEEPGRAM_API_KEY,
        ELEVENLABS_API_KEY,
    ])

    if not keys_ok:
        print("\nMissing API keys in .env file!")
        exit(1)

    print("\nFeatures:")
    print("  - AI Receptionist personality")
    print("  - Function calling (orders, hours, transfers, products)")
    print("  - Call logging to call_logs.json")
    print("\nTest:")
    print("  - Browser: https://agents-playground.livekit.io/")
    print("  - Phone: Call your Plivo number")
    print("=" * 60 + "\n")

    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            api_key=LIVEKIT_API_KEY,
            api_secret=LIVEKIT_API_SECRET,
            ws_url=LIVEKIT_URL,
        )
    )


if __name__ == "__main__":
    main()
