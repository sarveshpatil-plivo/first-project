"""
Week 2, Day 5: SIP Forward Server
Forwards Plivo calls to LiveKit via SIP.

Run: python3 sip_forward.py
Then expose via ngrok: ngrok http 5002
"""

import os
from flask import Flask, request, Response
from dotenv import load_dotenv

load_dotenv(dotenv_path="../.env")

app = Flask(__name__)

# Your LiveKit SIP URI (from LiveKit Cloud > SIP > Inbound Trunk)
# Format: sip:+<number>@<trunk-id>.sip.livekit.cloud
LIVEKIT_SIP_URI = os.getenv("LIVEKIT_SIP_URI", "sip:YOUR_SIP_URI_HERE")


@app.route("/sip-forward", methods=["POST", "GET"])
def sip_forward():
    """Forward incoming Plivo call to LiveKit SIP."""
    caller = request.values.get("From", "unknown")
    called_number = request.values.get("To", "+918035453216")
    print(f"Incoming call from {caller} to {called_number}, forwarding to LiveKit...")

    # Extract the SIP host from the URI
    sip_host = LIVEKIT_SIP_URI.replace("sip:", "").strip()

    # Ensure called number has + prefix
    if not called_number.startswith("+"):
        called_number = "+" + called_number

    # Include the called number in the SIP URI so LiveKit can match the trunk
    # Format: sip:+918035453216@3wl7o35eqw2.sip.livekit.cloud
    sip_uri_with_number = f"sip:{called_number}@{sip_host}"
    print(f"SIP URI: {sip_uri_with_number}")

    # Plivo XML to dial SIP URI (use <User> not <Sip>)
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak>Connecting you to our AI assistant. Please wait.</Speak>
    <Dial>
        <User>{sip_uri_with_number}</User>
    </Dial>
</Response>"""

    return Response(xml, mimetype="application/xml")


@app.route("/hangup", methods=["POST", "GET"])
def hangup():
    """Handle call hangup event."""
    caller = request.values.get("From", "unknown")
    duration = request.values.get("Duration", "0")
    print(f"Call ended - From: {caller}, Duration: {duration}s")
    return "", 200


@app.route("/health", methods=["GET"])
def health():
    """Health check."""
    return {"status": "ok", "sip_uri": LIVEKIT_SIP_URI[:50] + "..."}


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("SIP FORWARD SERVER")
    print("=" * 50)
    print(f"\nLiveKit SIP URI: {LIVEKIT_SIP_URI}")
    print("\nEndpoints:")
    print("  POST /sip-forward  - Plivo Answer URL")
    print("  GET  /health       - Health check")
    print("\nSteps:")
    print("1. Add LIVEKIT_SIP_URI to .env")
    print("2. Run: ngrok http 5002")
    print("3. Set Plivo Answer URL to: https://<ngrok>/sip-forward")
    print("=" * 50 + "\n")

    app.run(host="0.0.0.0", port=5002, debug=True)
