"""PostgreSQL database engine and session factory."""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

_raw_url = os.environ.get("DATABASE_URL", "postgresql://localhost:5432/gordie")

# Ensure we use psycopg v3 driver (not psycopg2)
DATABASE_URL = _raw_url.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine)


def get_session() -> Session:
    """Create and return a new database session."""
    return SessionLocal()
