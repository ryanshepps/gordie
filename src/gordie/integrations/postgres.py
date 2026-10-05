from collections.abc import Callable
from functools import cached_property
from pathlib import Path

from duckdb import DuckDBPyConnection
from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from gordie.agent.custom_checkpointer import CustomCheckpointer
from gordie.integrations.memory import environment_memory
from gordie.integrations.statistics import StatisticsFiles
from gordie.plugins import ConversationMemory


class PostgresStorage:
    def __init__(
        self,
        database_url: str,
        data_directory: Path,
        memory_factory: Callable[[], ConversationMemory] = environment_memory,
    ) -> None:
        self.database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        self.data_directory = data_directory
        self.memory_factory = memory_factory
        self._statistics = StatisticsFiles(data_directory)

    @cached_property
    def _engine(self) -> Engine:
        return create_engine(self.database_url, pool_size=10, max_overflow=20, pool_pre_ping=True)

    @cached_property
    def _sessions(self) -> sessionmaker[Session]:
        return sessionmaker(bind=self._engine)

    @cached_property
    def _checkpoint(self) -> CustomCheckpointer:
        return CustomCheckpointer()

    @cached_property
    def _memory(self) -> ConversationMemory:
        return self.memory_factory()

    def session(self) -> Session:
        return self._sessions()

    def checkpoint(self) -> BaseCheckpointSaver[str]:
        return self._checkpoint

    def memory(self) -> ConversationMemory:
        return self._memory

    def data_path(self, filename: str) -> Path:
        return self.data_directory / filename

    def stats_connection(self, filename: str) -> DuckDBPyConnection:
        return self._statistics.connection(filename)

    def reset_stats(self, filename: str) -> None:
        self._statistics.reset(filename)

    def prepare(self) -> None:
        from gordie.integrations.migrations import run_migrations

        run_migrations(database_url=self.database_url)

    def close(self) -> None:
        self._statistics.close()
        if "_checkpoint" in self.__dict__:
            self._checkpoint.close()
        if "_engine" in self.__dict__:
            self._engine.dispose()
