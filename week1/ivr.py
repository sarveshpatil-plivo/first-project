from flask import Blueprint, request, Response
from models import get_db, CallLog

ivr = Blueprint("ivr", __name__)


def xml_response(xml_content):
    """Return a Plivo XML response."""
    return Response(xml_content, mimetype="application/xml")


@ivr.route("/voice/incoming", methods=["GET", "POST"])
def incoming_call():
    """Handle incoming calls - play welcome message and menu."""
    caller = request.values.get("From", "unknown")

    # Log the call
    db = get_db()
    call = CallLog(caller_number=caller, call_status="answered")
    db.add(call)
    db.commit()
    db.close()

    # Get base URL for absolute paths
    base_url = "https://tamala-dilapidated-yaretzi.ngrok-free.dev"

    # Return IVR menu
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak>Welcome to our company.</Speak>
    <GetDigits action="{base_url}/voice/menu" method="POST" timeout="10" numDigits="1" retries="2">
        <Speak>Press 1 for Sales. Press 2 for Support. Press 3 to hear your caller ID.</Speak>
    </GetDigits>
    <Speak>We did not receive any input. Goodbye.</Speak>
</Response>"""

    return xml_response(xml)


@ivr.route("/voice/menu", methods=["GET", "POST"])
def handle_menu():
    """Handle menu selection."""
    digits = request.values.get("Digits", "")
    caller = request.values.get("From", "unknown")
    base_url = "https://tamala-dilapidated-yaretzi.ngrok-free.dev"

    # Update call status based on selection
    db = get_db()

    if digits == "1":
        # Update call log with status
        call = db.query(CallLog).filter(CallLog.caller_number == caller).order_by(CallLog.created_at.desc()).first()
        if call:
            call.call_status = "routed_sales"
            db.commit()
        db.close()

        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak>You pressed 1 for Sales. Our sales team is available Monday through Friday, 9 AM to 5 PM. Thank you for your interest.</Speak>
    <GetDigits action="{base_url}/voice/menu" method="POST" timeout="10" numDigits="1" retries="2">
        <Speak>To return to the main menu, press any key. Or hang up to end the call.</Speak>
    </GetDigits>
    <Speak>Goodbye.</Speak>
</Response>"""

    elif digits == "2":
        # Update call log with status
        call = db.query(CallLog).filter(CallLog.caller_number == caller).order_by(CallLog.created_at.desc()).first()
        if call:
            call.call_status = "routed_support"
            db.commit()
        db.close()

        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak>You pressed 2 for Support. For urgent issues, please email support at support@example.com. A team member will respond within 24 hours.</Speak>
    <GetDigits action="{base_url}/voice/menu" method="POST" timeout="10" numDigits="1" retries="2">
        <Speak>To return to the main menu, press any key. Or hang up to end the call.</Speak>
    </GetDigits>
    <Speak>Goodbye.</Speak>
</Response>"""

    elif digits == "3":
        db.close()
        # Read back the caller's phone number
        # Format phone number for speech (add spaces between digits)
        phone_for_speech = " ".join(caller.replace("+", ""))

        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak>Your caller ID is {phone_for_speech}.</Speak>
    <GetDigits action="{base_url}/voice/menu" method="POST" timeout="10" numDigits="1" retries="2">
        <Speak>Press 1 for Sales. Press 2 for Support. Press 3 to hear your caller ID again.</Speak>
    </GetDigits>
    <Speak>We did not receive any input. Goodbye.</Speak>
</Response>"""

    else:
        db.close()
        # Invalid input - replay menu
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak>Invalid option. Please try again.</Speak>
    <GetDigits action="{base_url}/voice/menu" method="POST" timeout="10" numDigits="1" retries="2">
        <Speak>Press 1 for Sales. Press 2 for Support. Press 3 to hear your caller ID.</Speak>
    </GetDigits>
    <Speak>Goodbye.</Speak>
</Response>"""

    return xml_response(xml)


@ivr.route("/voice/test", methods=["GET", "POST"])
def test_call():
    """Simple test endpoint - just speaks and hangs up."""
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak>Hello! This is a test call from your IVR system. Goodbye!</Speak>
</Response>"""
    return xml_response(xml)


@ivr.route("/voice/status", methods=["GET", "POST"])
def call_status():
    """Receive call status updates from Plivo."""
    call_uuid = request.values.get("CallUUID", "")
    status = request.values.get("CallStatus", "")

    print(f"Call {call_uuid}: {status}")

    return "", 200
