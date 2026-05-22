"""Tests for canonical user identity and thread repositories."""

from typing import cast
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from data.models import Medium
from data.thread_repository import ThreadRepository
from data.user_repository import UserRepository


class FakeResult:
    def __init__(self, row: tuple[object, ...] | None) -> None:
        self._row: tuple[object, ...] | None = row

    def fetchone(self) -> tuple[object, ...] | None:
        return self._row


FakeRow = tuple[object, ...] | None
FakeExecution = FakeRow | Exception


class FakeSession:
    def __init__(self, rows: list[FakeExecution]) -> None:
        self.rows: list[FakeExecution] = rows
        self.executed: list[dict[str, object]] = []
        self.commits: int = 0
        self.rollbacks: int = 0

    def execute(self, _query: object, params: dict[str, object] | None = None) -> FakeResult:
        self.executed.append(params or {})
        row = self.rows.pop(0) if self.rows else None
        if isinstance(row, Exception):
            raise row
        return FakeResult(row)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def test_get_by_identity_returns_user_row() -> None:
    user_id = UUID("7dc8bd5f-7d86-47c8-9a7a-3ad6c97c4e58")
    session = FakeSession(rows=[(user_id, "created")])
    repo = UserRepository(cast(Session, cast(object, session)))

    result = repo.get_by_identity(Medium.SMS, "+15551234567")

    assert result == (user_id, "created")
    assert session.executed[0] == {"medium": "sms", "external_id": "+15551234567"}


def test_create_with_identity_returns_existing_user_after_unique_conflict() -> None:
    attempted_user_id = UUID("7dc8bd5f-7d86-47c8-9a7a-3ad6c97c4e58")
    existing_user_id = UUID("8ec8bd5f-7d86-47c8-9a7a-3ad6c97c4e58")
    conflict = IntegrityError("insert identity", {}, Exception("duplicate"))
    session = FakeSession(rows=[(attempted_user_id,), conflict, (existing_user_id, "created")])
    repo = UserRepository(cast(Session, cast(object, session)))

    result = repo.create_with_identity(Medium.SMS, "+15551234567", "+15551234567")

    assert result == existing_user_id
    assert session.rollbacks == 1
    assert session.commits == 0


def test_thread_resolve_reuses_existing_user_medium_thread() -> None:
    user_id = UUID("7dc8bd5f-7d86-47c8-9a7a-3ad6c97c4e58")
    thread_id = UUID("8ec8bd5f-7d86-47c8-9a7a-3ad6c97c4e58")
    session = FakeSession(rows=[(thread_id, user_id, "sms", "created", "active"), None])
    repo = ThreadRepository(cast(Session, cast(object, session)))

    result = repo.resolve(user_id, Medium.SMS)

    assert result.thread_id == str(thread_id)
    assert result.is_new_thread is False
    assert session.executed[0] == {"user_id": user_id, "medium": "sms"}
    assert session.executed[1] == {"id": thread_id}
    assert session.commits == 1


def test_thread_resolve_returns_existing_thread_after_unique_conflict() -> None:
    user_id = UUID("7dc8bd5f-7d86-47c8-9a7a-3ad6c97c4e58")
    thread_id = UUID("8ec8bd5f-7d86-47c8-9a7a-3ad6c97c4e58")
    conflict = IntegrityError("insert thread", {}, Exception("duplicate"))
    session = FakeSession(
        rows=[None, conflict, (thread_id, user_id, "sms", "created", "active"), None]
    )
    repo = ThreadRepository(cast(Session, cast(object, session)))

    result = repo.resolve(user_id, Medium.SMS)

    assert result.thread_id == str(thread_id)
    assert result.is_new_thread is False
    assert session.rollbacks == 1
    assert session.commits == 1
