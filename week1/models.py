from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from config import DATABASE_URL

Base = declarative_base()


class CallLog(Base):
    """Stores information about each phone call."""
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
            "created_at": self.created_at.isoformat()
        }


class Visitor(Base):
    """Tracks website/API visitors."""
    __tablename__ = "visitors"

    id = Column(Integer, primary_key=True)
    session_id = Column(String(100), nullable=False)
    visit_count = Column(Integer, default=1)
    last_visit = Column(DateTime, default=datetime.utcnow)


# Database setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def init_db():
    """Create all tables."""
    Base.metadata.create_all(engine)


def get_db():
    """Get a database session."""
    db = SessionLocal()
    try:
        return db
    finally:
        pass  # Caller is responsible for closing
