"""Unit tests for temporary hosted trial routes."""

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import pytest
from quart import Quart
from quart.testing import QuartClient

from data.temporary_session_repository import (
    CreatedTemporarySession,
    TemporarySaveLink,
    TemporarySessionRecord,
    TrialProviderRequiredError,
)
from server.routes.trial_routes import register_trial_routes

SESSION_ID = UUID("11111111-1111-1111-1111-111111111111")
USER_ID = UUID("22222222-2222-2222-2222-222222222222")
SESSION = TemporarySessionRecord(
    id=SESSION_ID,
    user_id=USER_ID,
    question_count=0,
    question_limit=5,
    expires_at=datetime(2026, 5, 31, tzinfo=UTC),
)


class FakeTemporarySessionRepository:
    def close(self) -> None:
        pass

    def get_by_token(self, token: str) -> TemporarySessionRecord | None:
        return SESSION if token == "trial-token" else None

    def create_session(
        self,
        ttl_days: int = 7,
        question_limit: int = 5,
    ) -> CreatedTemporarySession:
        _ = ttl_days, question_limit
        return CreatedTemporarySession(session=SESSION, token="trial-token")

    def get_provider_connection(self, _session_id: UUID) -> None:
        return None

    def reserve_question(self, _session_id: UUID) -> None:
        raise TrialProviderRequiredError("Connect Yahoo Fantasy before asking a question")

    def create_save_link(self, _session_id: UUID, email: str) -> TemporarySaveLink:
        return TemporarySaveLink(email=email, token="save-token")


@pytest.fixture
def trial_client(monkeypatch: pytest.MonkeyPatch) -> QuartClient:
    app = Quart(__name__)
    monkeypatch.setattr(
        "server.routes.trial_routes.TemporarySessionRepository",
        FakeTemporarySessionRepository,
    )
    register_trial_routes(app)
    return cast(QuartClient, cast(object, app.test_client()))


@pytest.mark.asyncio
async def test_start_trial_session_sets_http_only_cookie(trial_client: QuartClient) -> None:
    response = await trial_client.post("/api/trial/session")

    body = cast(dict[str, object], await response.get_json())

    assert response.status_code == 200
    assert body["status"] == "active"
    assert body["session_token"] == "trial-token"
    assert "gordie_trial=trial-token" in response.headers["Set-Cookie"]
    assert "HttpOnly" in response.headers["Set-Cookie"]


@pytest.mark.asyncio
async def test_trial_question_requires_connected_provider(trial_client: QuartClient) -> None:
    response = await trial_client.post(
        "/api/trial/question",
        headers={"X-Gordie-Trial-Token": "trial-token"},
        json={"question": "Who should I start?"},
    )

    body = cast(dict[str, object], await response.get_json())

    assert response.status_code == 409
    assert body["error"] == "Connect Yahoo Fantasy before asking a question"


@pytest.mark.asyncio
async def test_trial_save_sends_magic_link(
    trial_client: QuartClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sent: list[dict[str, str]] = []

    class FakeEmailResult:
        success: bool = True
        error: str | None = None

    class FakeEmailService:
        def send_email(
            self,
            to_email: str,
            subject: str,
            text_body: str,
            html_body: str | None = None,
            track_opens: bool = True,
            track_clicks: bool = True,
        ) -> FakeEmailResult:
            _ = html_body, track_opens, track_clicks
            sent.append({"to": to_email, "subject": subject, "text": text_body})
            return FakeEmailResult()

    monkeypatch.setattr("server.email_service.EmailService", FakeEmailService)

    response = await trial_client.post(
        "/api/trial/save",
        headers={"X-Gordie-Trial-Token": "trial-token"},
        json={"email": "user@example.com"},
    )

    body = cast(dict[str, object], await response.get_json())

    assert response.status_code == 200
    assert body["status"] == "sent"
    assert sent[0]["to"] == "user@example.com"
    assert "save_token=save-token" in sent[0]["text"]
