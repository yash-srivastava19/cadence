"""Configuration and database session setup."""

from sqlalchemy.orm import Session, sessionmaker

from cadence.control.storage import engine


def get_session() -> Session:
    """Get database session."""
    SessionLocal = sessionmaker(bind=engine())
    return SessionLocal()
