"""Channel adapter contracts."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from agent.agent_state import AgentState
from data.models import Medium


class MessageFormat(StrEnum):
    PLAIN_TEXT = "plain_text"
    MARKDOWN = "markdown"
    HTML = "html"


@dataclass(frozen=True, slots=True)
class ChannelConstraints:
    max_length: int | None
    message_format: MessageFormat


@runtime_checkable
class ChannelAdapter(Protocol):
    @property
    def medium(self) -> Medium: ...

    @property
    def constraints(self) -> ChannelConstraints: ...

    def send(self, external_id: str, text: str, state: AgentState) -> None: ...


@dataclass(frozen=True, slots=True)
class AdapterRegistry:
    _adapters: Mapping[Medium, ChannelAdapter]

    def __post_init__(self) -> None:
        object.__setattr__(self, "_adapters", MappingProxyType(dict(self._adapters)))

    def get(self, medium: Medium) -> ChannelAdapter | None:
        return self._adapters.get(medium)
