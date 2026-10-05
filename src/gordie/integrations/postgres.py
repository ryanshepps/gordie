from functools import cached_property

from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from gordie.agent.custom_checkpointer import CustomCheckpointer


class PostgresStorage:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

    @cached_property
    def _engine(self) -> Engine:
        return create_engine(self.database_url, pool_size=10, max_overflow=20, pool_pre_ping=True)

    @cached_property
    def _sessions(self) -> sessionmaker[Session]:
        return sessionmaker(bind=self._engine)

    @cached_property
    def _checkpoint(self) -> CustomCheckpointer:
        return CustomCheckpointer()

    def session(self) -> Session:
        return self._sessions()

    def checkpoint(self) -> BaseCheckpointSaver[str]:
        return self._checkpoint

    def prepare(self) -> None:
        from gordie.integrations.migrations import run_migrations

        run_migrations(database_url=self.database_url)

    def close(self) -> None:
        if "_checkpoint" in self.__dict__:
            self._checkpoint.close()
        if "_engine" in self.__dict__:
            self._engine.dispose()
