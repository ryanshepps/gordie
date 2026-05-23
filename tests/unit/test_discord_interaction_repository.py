"""Tests for Discord interaction target repository."""

from typing import cast
from uuid import UUID

from sqlalchemy.orm import Session

from data.discord_interaction_repository import DiscordInteractionRepository


class FakeResult:
    def __init__(self, row: tuple[object, ...] | None) -> None:
        self._row = row

    def fetchone(self) -> tuple[object, ...] | None:
        return self._row


class FakeSession:
    def __init__(self, row: tuple[object, ...] | None = None) -> None:
        self.row = row
        self.executed: list[dict[str, object]] = []
        self.commits = 0

    def execute(self, _query: object, params: dict[str, object] | None = None) -> FakeResult:
        self.executed.append(params or {})
        return FakeResult(self.row)

    def commit(self) -> None:
        self.commits += 1


def test_upsert_target_saves_latest_interaction_target() -> None:
    thread_id = "7dc8bd5f-7d86-47c8-9a7a-3ad6c97c4e58"
    session = FakeSession()
    repo = DiscordInteractionRepository(cast(Session, cast(object, session)))

    repo.upsert_target(thread_id, "app-1", "token-1")

    assert session.executed[0] == {
        "thread_id": UUID(thread_id),
        "application_id": "app-1",
        "interaction_token": "token-1",
    }
    assert session.commits == 1


def test_get_target_returns_target_record() -> None:
    thread_id = UUID("7dc8bd5f-7d86-47c8-9a7a-3ad6c97c4e58")
    session = FakeSession((thread_id, "app-1", "token-1"))
    repo = DiscordInteractionRepository(cast(Session, cast(object, session)))

    target = repo.get_target(str(thread_id))

    assert target is not None
    assert target.thread_id == str(thread_id)
    assert target.application_id == "app-1"
    assert target.interaction_token == "token-1"
    assert session.executed[0] == {"thread_id": thread_id}


def test_get_target_returns_none_when_missing() -> None:
    thread_id = "7dc8bd5f-7d86-47c8-9a7a-3ad6c97c4e58"
    session = FakeSession()
    repo = DiscordInteractionRepository(cast(Session, cast(object, session)))

    assert repo.get_target(thread_id) is None
