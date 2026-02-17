"""
Week 2, Day 7: Voice AI Dashboard
Simple web UI to view call logs and system status.

Run: python3 dashboard.py
Open: http://localhost:5003
"""

import os
import json
from datetime import datetime
from flask import Flask, render_template_string, jsonify

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path="../.env")
except ImportError:
    pass

app = Flask(__name__)

CALL_LOG_FILE = "call_logs.json"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Voice AI Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #fff;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 {
            text-align: center;
            margin-bottom: 30px;
            font-size: 2.5em;
            background: linear-gradient(90deg, #00d9ff, #00ff88);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 25px;
            text-align: center;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
        }
        .stat-card h3 { color: #888; font-size: 0.9em; margin-bottom: 10px; }
        .stat-card .value { font-size: 2.5em; font-weight: bold; color: #00d9ff; }
        .status-badge {
            display: inline-block;
            padding: 8px 20px;
            border-radius: 20px;
            font-weight: bold;
            margin-top: 10px;
        }
        .status-online { background: #00ff88; color: #000; }
        .status-offline { background: #ff4757; color: #fff; }
        .section {
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .section h2 { margin-bottom: 20px; color: #00d9ff; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.1); }
        th { color: #888; font-weight: normal; }
        .feature-list { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; }
        .feature {
            background: rgba(0,217,255,0.1);
            padding: 15px;
            border-radius: 10px;
            border-left: 3px solid #00d9ff;
        }
        .feature strong { color: #00d9ff; }
        .phone-number {
            font-size: 1.5em;
            color: #00ff88;
            font-weight: bold;
        }
        .refresh-btn {
            background: #00d9ff;
            color: #000;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: bold;
        }
        .refresh-btn:hover { background: #00ff88; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Voice AI Dashboard</h1>

        <div class="stats">
            <div class="stat-card">
                <h3>SYSTEM STATUS</h3>
                <span class="status-badge status-online">ONLINE</span>
            </div>
            <div class="stat-card">
                <h3>TOTAL CALLS</h3>
                <div class="value" id="total-calls">{{ total_calls }}</div>
            </div>
            <div class="stat-card">
                <h3>PHONE NUMBER</h3>
                <div class="phone-number">+91 80354 53216</div>
            </div>
            <div class="stat-card">
                <h3>DEPLOYMENT</h3>
                <div class="value" style="font-size: 1.2em;">Railway</div>
            </div>
        </div>

        <div class="section">
            <h2>AI Agent Capabilities</h2>
            <div class="feature-list">
                <div class="feature"><strong>Order Status</strong> - Check order tracking</div>
                <div class="feature"><strong>Business Hours</strong> - Get availability info</div>
                <div class="feature"><strong>Product Lookup</strong> - Search products & prices</div>
                <div class="feature"><strong>Schedule Callback</strong> - Request human callback</div>
                <div class="feature"><strong>Transfer Calls</strong> - Route to departments</div>
                <div class="feature"><strong>Smart Hangup</strong> - End calls gracefully</div>
            </div>
        </div>

        <div class="section">
            <h2>Architecture</h2>
            <pre style="color: #00d9ff; font-size: 0.9em;">
Phone Call → Plivo → SIP Forward → LiveKit Cloud → AI Agent (Railway)
                                        ↓
                    ┌──────────────────────────────────────┐
                    │  Deepgram (STT) → GPT-4o → ElevenLabs (TTS)  │
                    └──────────────────────────────────────┘
            </pre>
        </div>

        <div class="section">
            <h2>Recent Call Logs <button class="refresh-btn" onclick="location.reload()">Refresh</button></h2>
            <table>
                <thead>
                    <tr><th>Time</th><th>Room</th><th>Event</th><th>Details</th></tr>
                </thead>
                <tbody id="logs-table">
                    {% for log in logs %}
                    <tr>
                        <td>{{ log.timestamp[:19] }}</td>
                        <td>{{ log.room[:20] }}...</td>
                        <td>{{ log.event }}</td>
                        <td>{{ log.details }}</td>
                    </tr>
                    {% endfor %}
                    {% if not logs %}
                    <tr><td colspan="4" style="text-align: center; color: #888;">No calls yet</td></tr>
                    {% endif %}
                </tbody>
            </table>
        </div>

        <div class="section" style="text-align: center;">
            <h2>Test the System</h2>
            <p style="margin: 20px 0; color: #888;">Call the number above and try these phrases:</p>
            <div class="feature-list" style="max-width: 600px; margin: 0 auto;">
                <div class="feature">"What are your business hours?"</div>
                <div class="feature">"Check order ORD-12345"</div>
                <div class="feature">"How much is the widget?"</div>
                <div class="feature">"Transfer me to sales"</div>
            </div>
        </div>
    </div>
</body>
</html>
"""


def get_call_logs():
    """Load call logs from file."""
    if os.path.exists(CALL_LOG_FILE):
        try:
            with open(CALL_LOG_FILE, "r") as f:
                logs = json.load(f)
                return logs[-20:]  # Last 20 logs
        except:
            pass
    return []


@app.route("/")
def dashboard():
    """Main dashboard page."""
    logs = get_call_logs()
    return render_template_string(HTML_TEMPLATE, logs=logs, total_calls=len(logs))


@app.route("/api/logs")
def api_logs():
    """API endpoint for logs."""
    return jsonify(get_call_logs())


@app.route("/api/status")
def api_status():
    """API endpoint for status."""
    return jsonify({
        "status": "online",
        "agent": "LiveKit AI Receptionist",
        "deployment": "Railway",
        "phone": "+91 80354 53216"
    })


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("VOICE AI DASHBOARD")
    print("=" * 50)
    print("\nOpen: http://localhost:5003")
    print("=" * 50 + "\n")

    app.run(host="0.0.0.0", port=5003, debug=True)
