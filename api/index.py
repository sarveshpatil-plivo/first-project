import os
import sys
import json
from datetime import datetime

# Add parent directory to path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, jsonify, request, Response
from dotenv import load_dotenv
from plivo import plivoxml

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "vercel-secret-key-change-this")

# Base URL for Plivo callbacks
BASE_URL = os.getenv("BASE_URL", "https://demo-ivr.vercel.app")

# ============ Redis Setup ============
REDIS_URL = os.getenv("REDIS_URL")
redis_client = None
redis_error = None

if REDIS_URL:
    try:
        import redis
        redis_client = redis.from_url(REDIS_URL)
        redis_client.ping()
    except Exception as e:
        redis_error = str(e)
        redis_client = None

SESSION_TTL = 1800  # 30 minutes


def save_session(caller_id, step):
    """Save or update caller session in Redis."""
    if not redis_client:
        return

    key = f"session:{caller_id}"
    existing = redis_client.get(key)

    if existing:
        data = json.loads(existing.decode())
        data["step"] = step
        data["updated_at"] = datetime.utcnow().isoformat()
    else:
        data = {
            "caller_id": caller_id,
            "step": step,
            "started_at": datetime.utcnow().isoformat()
        }

    redis_client.setex(key, SESSION_TTL, json.dumps(data))


# ============ Database Setup ============
DATABASE_URL = os.getenv("DATABASE_URL", "")

if "postgresql" in DATABASE_URL or "postgres" in DATABASE_URL:
    from sqlalchemy import create_engine, Column, Integer, String, DateTime, text
    from sqlalchemy.orm import sessionmaker, declarative_base

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
    Base.metadata.create_all(engine)

    def get_db():
        return SessionLocal()
else:
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


# ============ IVR Routes (Using Plivo SDK) ============

def xml_response(response_element):
    """Convert Plivo ResponseElement to Flask Response."""
    return Response(response_element.to_string(), mimetype="application/xml")


@app.route("/api/answer", methods=["GET", "POST"])
@app.route("/voice/incoming", methods=["GET", "POST"])
def answer_call():
    """Plivo calls this when someone dials in."""
    caller = request.values.get("From", "unknown")

    # Log call start in PostgreSQL
    db = get_db()
    call = CallLog(caller_number=caller, call_status="answered")
    db.add(call)
    db.commit()
    db.close()

    # Store call session in Redis (current step = "main_menu")
    save_session(caller, "main_menu")

    # Build XML response using Plivo SDK
    response = plivoxml.ResponseElement()
    response.add(plivoxml.SpeakElement("Welcome to Acme Corp."))

    get_digits = plivoxml.GetDigitsElement(
        action=f"{BASE_URL}/api/handle-input",
        method="POST",
        timeout=10,
        num_digits=1
    )
    get_digits.add(plivoxml.SpeakElement("Press 1 for Sales. Press 2 for Support. Press 3 to hear your caller ID."))
    response.add(get_digits)

    response.add(plivoxml.SpeakElement("We did not receive any input. Goodbye."))

    return xml_response(response)


@app.route("/api/handle-input", methods=["GET", "POST"])
@app.route("/voice/menu", methods=["GET", "POST"])
def handle_input():
    """Plivo calls this with digit pressed."""
    digits = request.values.get("Digits", "")
    caller = request.values.get("From", "unknown")

    response = plivoxml.ResponseElement()

    if digits == "1":
        # Update session and call log
        save_session(caller, "routed_sales")
        update_call_status(caller, "routed_sales")

        response.add(plivoxml.SpeakElement("Connecting to sales. Goodbye."))

    elif digits == "2":
        # Update session and call log
        save_session(caller, "routed_support")
        update_call_status(caller, "routed_support")

        response.add(plivoxml.SpeakElement("Connecting to support. Goodbye."))

    elif digits == "3":
        # Read caller's phone number back
        save_session(caller, "caller_id_readback")
        phone_for_speech = " ".join(caller.replace("+", ""))

        response.add(plivoxml.SpeakElement(f"Your caller ID is {phone_for_speech}."))

        get_digits = plivoxml.GetDigitsElement(
            action=f"{BASE_URL}/api/handle-input",
            method="POST",
            timeout=10,
            num_digits=1
        )
        get_digits.add(plivoxml.SpeakElement("Press 1 for Sales. Press 2 for Support. Press 3 to hear your caller ID again."))
        response.add(get_digits)
        response.add(plivoxml.SpeakElement("We did not receive any input. Goodbye."))

    else:
        # Invalid input - redirect back to /api/answer
        save_session(caller, "invalid_input")

        response.add(plivoxml.SpeakElement("Invalid option."))
        response.add(plivoxml.RedirectElement(f"{BASE_URL}/api/answer"))

    return xml_response(response)


def update_call_status(caller, status):
    """Update call log with status."""
    if "postgresql" not in DATABASE_URL and "postgres" not in DATABASE_URL:
        return

    try:
        db = get_db()
        call = db.query(CallLog).filter(
            CallLog.caller_number == caller
        ).order_by(CallLog.created_at.desc()).first()
        if call:
            call.call_status = status
            db.commit()
        db.close()
    except:
        pass


@app.route("/voice/status", methods=["GET", "POST"])
def call_status():
    """Receive call status updates from Plivo."""
    return "", 200


# ============ API Routes ============

@app.route("/")
def home():
    return jsonify({
        "message": "IVR System - Running on Vercel",
        "status": "healthy",
        "endpoints": {
            "/": "This page",
            "/health": "Health check with Redis & DB status",
            "/api/answer": "Plivo webhook for incoming calls",
            "/api/handle-input": "Plivo webhook for digit input",
            "/api/call-history/<phone>": "Get calls from specific number",
            "/sessions": "View active Redis sessions"
        }
    })


@app.route("/health")
@app.route("/api/health")
def health():
    result = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "platform": "vercel",
        "checks": {}
    }

    # Check PostgreSQL
    if "postgresql" in DATABASE_URL or "postgres" in DATABASE_URL:
        try:
            db = get_db()
            db.execute(text("SELECT 1"))
            db.close()
            result["checks"]["database"] = "ok"
        except Exception as e:
            result["checks"]["database"] = f"error: {str(e)}"
            result["status"] = "unhealthy"
    else:
        result["checks"]["database"] = "not configured"

    # Check Redis
    if redis_client:
        try:
            redis_client.ping()
            result["checks"]["redis"] = "ok"
        except Exception as e:
            result["checks"]["redis"] = f"error: {str(e)}"
            result["status"] = "unhealthy"
    elif REDIS_URL:
        result["checks"]["redis"] = f"connection failed: {redis_error}"
    else:
        result["checks"]["redis"] = "not configured (no REDIS_URL)"

    return jsonify(result)


@app.route("/calls", methods=["GET", "POST"])
@app.route("/api/log-call", methods=["POST"])
@app.route("/api/call-logs", methods=["GET"])
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
@app.route("/api/call-history/<phone_number>")
def call_history(phone_number):
    """Get call history for a specific phone number."""
    db = get_db()

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


@app.route("/sessions")
def list_sessions():
    """List all active call sessions in Redis."""
    if not redis_client:
        return jsonify({"error": "Redis not configured"}), 503

    keys = redis_client.keys("session:*")
    sessions = []

    for key in keys:
        caller_id = key.decode().replace("session:", "")
        data = redis_client.get(key)
        ttl = redis_client.ttl(key)

        if data:
            session_data = json.loads(data.decode())
            sessions.append({
                "caller_id": caller_id,
                "session": session_data,
                "ttl_remaining": ttl
            })

    return jsonify({
        "count": len(sessions),
        "sessions": sessions
    })


# Vercel handler
if __name__ == "__main__":
    app.run(debug=True, port=5001)
