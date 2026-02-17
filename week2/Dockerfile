FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including audio libraries
RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    ffmpeg \
    libavcodec-dev \
    libavformat-dev \
    libavutil-dev \
    libswresample-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements-livekit.txt .
RUN pip install --no-cache-dir -r requirements-livekit.txt

# Copy application
COPY livekit_agent.py .
COPY elevenlabs_http_tts.py .

# Run the agent
CMD ["python", "livekit_agent.py", "start"]
