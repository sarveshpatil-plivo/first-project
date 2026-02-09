import os
import redis
from flask import Flask, jsonify, request, session, render_template
from dotenv import load_dotenv
from models import init_db, get_db, CallLog, Visitor
from datetime import datetime
from ivr import ivr

load_dotenv()

app = Flask(__name__)
app.register_blueprint(ivr)  # Register IVR routes
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")

# Redis connection (optional - for session caching)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_client = None
try:
    redis_client = redis.from_url(REDIS_URL)
    redis_client.ping()
    print("✓ Connected to Redis")
except:
    print("⚠ Redis not available, using local sessions")
    redis_client = None


@app.route("/simulator")
def simulator():
    """IVR phone simulator - test the IVR without real calls."""
    return render_template("simulator.html")


@app.route("/call")
def call_page():
    """Call trigger UI."""
    return render_template("call.html")


@app.route("/make-call", methods=["POST"])
def make_call():
    """Trigger an outbound call to the specified number."""
    import plivo
    from config import PLIVO_AUTH_ID, PLIVO_AUTH_TOKEN

    data = request.get_json() or {}
    phone = data.get("phone", "").strip()
    use_local = data.get("use_local", False)

    if not phone:
        return jsonify({"success": False, "error": "Phone number required"}), 400

    # Ensure phone has + prefix
    if not phone.startswith("+"):
        phone = "+" + phone

    try:
        client = plivo.RestClient(PLIVO_AUTH_ID, PLIVO_AUTH_TOKEN)

        # Use Vercel by default, or ngrok for local testing
        if use_local:
            base_url = os.getenv("NGROK_URL", "https://tamala-dilapidated-yaretzi.ngrok-free.dev")
        else:
            base_url = "https://demo-ivr.vercel.app"

        response = client.calls.create(
            from_="+918035453216",
            to_=phone,
            answer_url=f"{base_url}/voice/incoming",
            answer_method="POST"
        )

        return jsonify({
            "success": True,
            "message": "Call initiated",
            "call_uuid": response.request_uuid,
            "using": "local (ngrok)" if use_local else "Vercel"
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/")
def home():
    """Home page - tracks visitors."""
    # Track visit count using session
    if "visit_count" not in session:
        session["visit_count"] = 0
    session["visit_count"] += 1

    # Also cache in Redis if available
    if redis_client:
        redis_client.incr("total_visits")
        total = redis_client.get("total_visits").decode()
    else:
        total = "N/A (Redis not connected)"

    return jsonify({
        "message": "Welcome to your Flask API!",
        "your_visits": session["visit_count"],
        "total_site_visits": total,
        "endpoints": {
            "/": "This page",
            "/health": "Health check",
            "/calls": "View all call logs (GET) or add a call (POST)",
            "/calls/<id>": "View specific call"
        }
    })


@app.route("/health")
def health():
    """Health check endpoint with actual connectivity tests."""
    from datetime import datetime as dt

    result = {
        "status": "healthy",
        "timestamp": dt.utcnow().isoformat(),
        "checks": {}
    }

    # Test PostgreSQL/Database
    try:
        from sqlalchemy import text
        db = get_db()
        db.execute(text("SELECT 1"))  # Simple query to test connection
        db.close()
        result["checks"]["database"] = "ok"
    except Exception as e:
        result["checks"]["database"] = f"error: {str(e)}"
        result["status"] = "unhealthy"

    # Test Redis
    if redis_client:
        try:
            redis_client.ping()
            result["checks"]["redis"] = "ok"
        except Exception as e:
            result["checks"]["redis"] = f"error: {str(e)}"
            result["status"] = "unhealthy"
    else:
        result["checks"]["redis"] = "not configured"

    return jsonify(result)


@app.route("/calls", methods=["GET", "POST"])
def calls():
    """List all calls or log a new call."""
    db = get_db()

    if request.method == "POST":
        # Log a new call
        data = request.get_json() or {}
        caller = data.get("caller_number", "unknown")

        call = CallLog(caller_number=caller, call_status="received")
        db.add(call)
        db.commit()
        db.refresh(call)

        return jsonify({"message": "Call logged", "call": call.to_dict()}), 201

    # GET - list all calls
    all_calls = db.query(CallLog).order_by(CallLog.created_at.desc()).limit(50).all()
    db.close()

    return jsonify({
        "count": len(all_calls),
        "calls": [c.to_dict() for c in all_calls]
    })


@app.route("/calls/<int:call_id>")
def get_call(call_id):
    """Get a specific call by ID."""
    db = get_db()
    call = db.query(CallLog).filter(CallLog.id == call_id).first()
    db.close()

    if not call:
        return jsonify({"error": "Call not found"}), 404

    return jsonify(call.to_dict())


# ============ Redis Session Management ============
# Day 4 Project 3: Redis for Call State

import json
from datetime import datetime as dt

SESSION_TTL = 1800  # 30 minutes in seconds


@app.route("/start-session/<caller_id>", methods=["GET", "POST"])
def start_session(caller_id):
    """Start a new call session in Redis."""
    if not redis_client:
        return jsonify({"error": "Redis not configured"}), 503

    session_data = {
        "step": "greeting",
        "started_at": dt.utcnow().isoformat(),
        "caller_id": caller_id
    }

    key = f"session:{caller_id}"
    redis_client.setex(key, SESSION_TTL, json.dumps(session_data))

    return jsonify({
        "message": "Session started",
        "caller_id": caller_id,
        "session": session_data,
        "ttl_seconds": SESSION_TTL
    })


@app.route("/get-session/<caller_id>")
def get_session(caller_id):
    """Retrieve a call session from Redis."""
    if not redis_client:
        return jsonify({"error": "Redis not configured"}), 503

    key = f"session:{caller_id}"
    data = redis_client.get(key)

    if not data:
        return jsonify({"error": "Session not found", "caller_id": caller_id}), 404

    session_data = json.loads(data.decode())
    ttl = redis_client.ttl(key)

    return jsonify({
        "caller_id": caller_id,
        "session": session_data,
        "ttl_remaining": ttl
    })


@app.route("/update-session/<caller_id>/<step>", methods=["GET", "POST"])
def update_session(caller_id, step):
    """Update the step in a call session."""
    if not redis_client:
        return jsonify({"error": "Redis not configured"}), 503

    key = f"session:{caller_id}"
    data = redis_client.get(key)

    if not data:
        return jsonify({"error": "Session not found", "caller_id": caller_id}), 404

    session_data = json.loads(data.decode())
    old_step = session_data.get("step")
    session_data["step"] = step
    session_data["updated_at"] = dt.utcnow().isoformat()

    # Preserve TTL
    ttl = redis_client.ttl(key)
    if ttl > 0:
        redis_client.setex(key, ttl, json.dumps(session_data))
    else:
        redis_client.setex(key, SESSION_TTL, json.dumps(session_data))

    return jsonify({
        "message": "Session updated",
        "caller_id": caller_id,
        "old_step": old_step,
        "new_step": step,
        "session": session_data
    })


@app.route("/delete-session/<caller_id>", methods=["GET", "POST", "DELETE"])
def delete_session(caller_id):
    """Delete a call session from Redis."""
    if not redis_client:
        return jsonify({"error": "Redis not configured"}), 503

    key = f"session:{caller_id}"
    deleted = redis_client.delete(key)

    return jsonify({
        "message": "Session deleted" if deleted else "Session not found",
        "caller_id": caller_id,
        "deleted": bool(deleted)
    })


@app.route("/list-sessions")
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


# ============ Call History Endpoint ============
# Day 4 Project 4: Call history by phone number

@app.route("/call-history/<phone_number>")
def call_history(phone_number):
    """Get call history for a specific phone number."""
    db = get_db()

    # Clean phone number (remove spaces, ensure + prefix)
    phone = phone_number.strip().replace(" ", "")
    if not phone.startswith("+"):
        phone = "+" + phone

    # Query calls from this number
    calls = db.query(CallLog).filter(
        CallLog.caller_number == phone
    ).order_by(CallLog.created_at.desc()).limit(50).all()

    db.close()

    return jsonify({
        "phone_number": phone,
        "total_calls": len(calls),
        "calls": [c.to_dict() for c in calls]
    })


if __name__ == "__main__":
    print("Initializing database...")
    init_db()
    print("✓ Database ready")
    print("\nStarting server at http://localhost:5001")
    print("Press Ctrl+C to stop\n")
    app.run(debug=True, port=5001)
