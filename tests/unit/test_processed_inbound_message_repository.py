"""Tests for inbound message idempotency repository."""

from typing import cast

from sqlalchemy.orm import Session

from data.models import Medium
from data.processed_inbound_message_repository import ProcessedInboundMessageRepository


class FakeResult:
    def __init__(self, row: tuple[object, ...] | None) -> None:
        self._row: tuple[object, ...] | None = row

    def fetchone(self) -> tuple[object, ...] | None:
        return self._row


class FakeSession:
    def __init__(self, row: tuple[object, ...] | None) -> None:
        self._row: tuple[object, ...] | None = row
        self.executed: list[dict[str, object]] = []
        self.commits: int = 0

    def execute(self, _query: object, params: dict[str, object] | None = None) -> FakeResult:
        self.executed.append(params or {})
        return FakeResult(self._row)

    def commit(self) -> None:
        self.commits += 1


def test_claim_returns_true_for_new_message() -> None:
    session = FakeSession((1,))
    repo = ProcessedInboundMessageRepository(cast(Session, cast(object, session)))

    claimed = repo.claim(Medium.SMS, "sinch-1", "+15551234567")

    assert claimed is True
    assert session.executed[0] == {
        "medium": "sms",
        "external_message_id": "sinch-1",
        "external_sender_id": "+15551234567",
    }
    assert session.commits == 1


def test_claim_returns_false_for_duplicate_message() -> None:
    session = FakeSession(None)
    repo = ProcessedInboundMessageRepository(cast(Session, cast(object, session)))

    claimed = repo.claim(Medium.EMAIL, "mailgun-1", "user@test.com")

    assert claimed is False
    assert session.executed[0] == {
        "medium": "email",
        "external_message_id": "mailgun-1",
        "external_sender_id": "user@test.com",
    }
    assert session.commits == 1
