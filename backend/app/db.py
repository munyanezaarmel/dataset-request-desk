from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

# The engine manages a pool of connections to Postgres.
engine = create_engine(settings.database_url, pool_pre_ping=True)

# A session is one "conversation" with the database (one per web request).
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    """All our table classes will inherit from this (Step 2)."""


def get_db():
    """FastAPI dependency: give each request its own session, always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        