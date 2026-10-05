from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from quart import Quart
from sqlalchemy.orm import Session

from gordie.data.models import Medium


@dataclass(frozen=True, slots=True)
class MessageContext:
    user_id: str
    thread_id: str
    external_id: str
    recipient: str
    channel: Medium = Medium.EMAIL


@dataclass(frozen=True, slots=True)
class IncomingMessage:
    context: MessageContext
    text: str


@dataclass(frozen=True, slots=True)
class OutgoingMessage:
    context: MessageContext
    text: str


MessageHandler = Callable[[IncomingMessage], Awaitable[OutgoingMessage | None]]


class Communication(Protocol):
    def register(self, app: Quart, handle_message: MessageHandler) -> None: ...
    def start(self) -> None: ...
    def send(self, message: OutgoingMessage) -> None: ...
    def close(self) -> None: ...


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


class Storage(Protocol):
    def session(self) -> Session: ...
    def checkpoint(self) -> BaseCheckpointSaver[str]: ...
    def prepare(self) -> None: ...
    def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class Plugins:
    storage: Storage
    access: AccessPolicy = field(default_factory=UnrestrictedAccess)
    extra_tools: tuple[BaseTool, ...] = ()
    communication: Communication | None = None
