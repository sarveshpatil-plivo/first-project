import os
from dotenv import load_dotenv

load_dotenv()

PLIVO_AUTH_ID = os.getenv("PLIVO_AUTH_ID")
PLIVO_AUTH_TOKEN = os.getenv("PLIVO_AUTH_TOKEN")

# Database - uses SQLite locally, PostgreSQL in production
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///local.db")

# Redis - optional, for session caching
REDIS_URL = os.getenv("REDIS_URL")

# Flask secret key
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
