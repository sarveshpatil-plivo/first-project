import os
import sys

# Add parent directory to path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, jsonify, request, session, render_template
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, template_folder='../templates')
app.secret_key = os.getenv("SECRET_KEY", "vercel-secret-key-change-this")

# Database URL - use PostgreSQL in production
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///local.db")

# Import and configure database only if not SQLite (Vercel doesn't persist files)
if "postgresql" in DATABASE_URL:
    from sqlalchemy import create_engine, Column, Integer, String, DateTime
    from sqlalchemy.orm import sessionmaker, declarative_base
    from datetime import datetime

    Base = declarative_base()

    class CallLog(Base):
        __tablename__ = "call_logs"
        id = Column(Integer, primary_key=True)
        caller_number = Column(String(20), nullable=False)
        call_status = Column(String(50), default="received")
        created_at = Column(DateTime, default=datetime.utcnow)

        def to_dict(self):
            return {
                "id": self.id,
                "caller_number": self.caller_number,
                "call_status": self.call_status,
                "created_at": self.created_at.isoformat() if self.created_at else None
            }

    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)

    # Create tables
    Base.metadata.create_all(engine)

    def get_db():
        return SessionLocal()
else:
    # Mock for serverless without DB
    class CallLog:
        def __init__(self, **kwargs):
            self.id = 1
            self.caller_number = kwargs.get('caller_number', 'unknown')
            self.call_status = kwargs.get('call_status', 'received')
        def to_dict(self):
            return {"id": self.id, "caller_number": self.caller_number, "call_status": self.call_status}

    class MockDB:
        def add(self, obj): pass
        def commit(self): pass
        def close(self): pass
        def refresh(self, obj): pass
        def query(self, model): return self
        def filter(self, *args): return self
        def order_by(self, *args): return self
        def limit(self, n): return self
        def first(self): return None
        def all(self): return []

    def get_db():
        return MockDB()


# ============ IVR Routes ============

def xml_response(xml_content):
    from flask import Response
    return Response(xml_content, mimetype="application/xml")


@app.route("/voice/incoming", methods=["GET", "POST"])
def incoming_call():
    caller = request.values.get("From", "unknown")

    db = get_db()
    call = CallLog(caller_number=caller, call_status="answered")
    db.add(call)
    db.commit()
    db.close()

    base_url = "https://demo-ivr.vercel.app"

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak>Welcome to our company.</Speak>
    <GetDigits action="{base_url}/voice/menu" method="POST" timeout="10" numDigits="1" retries="2">
        <Speak>Press 1 for Sales. Press 2 for Support. Press 3 to hear your caller ID.</Speak>
    </GetDigits>
    <Speak>We did not receive any input. Goodbye.</Speak>
</Response>"""

    return xml_response(xml)


@app.route("/voice/menu", methods=["GET", "POST"])
def handle_menu():
    digits = request.values.get("Digits", "")
    caller = request.values.get("From", "unknown")
    base_url = "https://demo-ivr.vercel.app"

    if digits == "1":
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak>You pressed 1 for Sales. Our sales team is available Monday through Friday, 9 AM to 5 PM. Thank you for your interest.</Speak>
    <GetDigits action="{base_url}/voice/menu" method="POST" timeout="10" numDigits="1" retries="2">
        <Speak>To return to the main menu, press any key. Or hang up to end the call.</Speak>
    </GetDigits>
    <Speak>Goodbye.</Speak>
</Response>"""

    elif digits == "2":
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak>You pressed 2 for Support. For urgent issues, please email support at support@example.com. A team member will respond within 24 hours.</Speak>
    <GetDigits action="{base_url}/voice/menu" method="POST" timeout="10" numDigits="1" retries="2">
        <Speak>To return to the main menu, press any key. Or hang up to end the call.</Speak>
    </GetDigits>
    <Speak>Goodbye.</Speak>
</Response>"""

    elif digits == "3":
        # Read back the caller's phone number
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
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak>Invalid option. Please try again.</Speak>
    <GetDigits action="{base_url}/voice/menu" method="POST" timeout="10" numDigits="1" retries="2">
        <Speak>Press 1 for Sales. Press 2 for Support. Press 3 to hear your caller ID.</Speak>
    </GetDigits>
    <Speak>Goodbye.</Speak>
</Response>"""

    return xml_response(xml)


@app.route("/voice/status", methods=["GET", "POST"])
def call_status():
    return "", 200


# ============ API Routes ============

@app.route("/")
def home():
    return jsonify({
        "message": "IVR System - Running on Vercel",
        "status": "healthy",
        "endpoints": {
            "/": "This page",
            "/health": "Health check",
            "/voice/incoming": "Plivo webhook for incoming calls",
            "/voice/menu": "Plivo webhook for menu handling",
            "/simulator": "IVR phone simulator"
        }
    })


@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "database": "postgresql" if "postgresql" in DATABASE_URL else "mock",
        "platform": "vercel"
    })


@app.route("/simulator")
def simulator():
    return render_template("simulator.html")


@app.route("/calls", methods=["GET", "POST"])
def calls():
    db = get_db()

    if request.method == "POST":
        data = request.get_json() or {}
        caller = data.get("caller_number", "unknown")
        call = CallLog(caller_number=caller, call_status="received")
        db.add(call)
        db.commit()
        return jsonify({"message": "Call logged", "call": call.to_dict()}), 201

    all_calls = db.query(CallLog).order_by(CallLog.created_at.desc()).limit(50).all()
    db.close()
    return jsonify({"count": len(all_calls), "calls": [c.to_dict() for c in all_calls]})


@app.route("/call-history/<phone_number>")
def call_history(phone_number):
    """Get call history for a specific phone number."""
    db = get_db()

    # Clean phone number
    phone = phone_number.strip().replace(" ", "")
    if not phone.startswith("+"):
        phone = "+" + phone

    calls = db.query(CallLog).filter(
        CallLog.caller_number == phone
    ).order_by(CallLog.created_at.desc()).limit(50).all()

    db.close()

    return jsonify({
        "phone_number": phone,
        "total_calls": len(calls),
        "calls": [c.to_dict() for c in calls]
    })


# Vercel handler
if __name__ == "__main__":
    app.run(debug=True, port=5001)
