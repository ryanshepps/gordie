import os
from functools import cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


@cache
def session_factory() -> sessionmaker[Session]:
    url = os.environ.get("DATABASE_URL", "postgresql://localhost:5432/fantasy_agent")
    url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    engine = create_engine(url, pool_size=10, max_overflow=20, pool_pre_ping=True)
    return sessionmaker(bind=engine)


def get_session() -> Session:
    return session_factory()()
