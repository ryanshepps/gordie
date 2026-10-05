from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from apscheduler.schedulers.background import BackgroundScheduler
from duckdb import DuckDBPyConnection
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.store.base import BaseStore
from quart import Quart
from sqlalchemy.orm import Session


class Action(StrEnum):
    QUESTION = "question"
    CONNECT_TEAM = "connect_team"


@dataclass(frozen=True, slots=True)
class AccessRequest:
    user_id: str
    action: Action
    message: str = ""


@dataclass(frozen=True, slots=True)
class AccessDecision:
    allowed: bool
    response: str = ""


class AccessPolicy(Protocol):
    def evaluate(self, request: AccessRequest) -> AccessDecision: ...


@dataclass(frozen=True, slots=True)
class UnrestrictedAccess:
    def evaluate(self, request: AccessRequest) -> AccessDecision:
        return AccessDecision(allowed=True)


@dataclass(frozen=True, slots=True)
class ConversationMemory:
    store: BaseStore
    search_enabled: bool = False


class Storage(Protocol):
    def session(self) -> Session: ...
    def checkpoint(self) -> BaseCheckpointSaver[str]: ...
    def memory(self) -> ConversationMemory: ...
    def data_path(self, filename: str) -> Path: ...
    def stats_connection(self, filename: str) -> DuckDBPyConnection: ...
    def reset_stats(self, filename: str) -> None: ...
    def prepare(self) -> None: ...
    def close(self) -> None: ...


class Models(Protocol):
    def chat(self, *, temperature: float = 0, model: str | None = None) -> BaseChatModel: ...


RouteRegistrar = Callable[[Quart], None]
JobRegistrar = Callable[[BackgroundScheduler], None]


@dataclass(frozen=True, slots=True)
class Plugins:
    storage: Storage
    models: Models
    access: AccessPolicy = field(default_factory=UnrestrictedAccess)
    tools: tuple[BaseTool, ...] = ()
    routes: tuple[RouteRegistrar, ...] = ()
    jobs: tuple[JobRegistrar, ...] = ()
