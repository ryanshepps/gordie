"""Public Yahoo callback and route behavior after transport retirement."""

from typing import cast
from unittest.mock import MagicMock, patch
from uuid import UUID

from apscheduler.schedulers.background import BackgroundScheduler
from quart import Quart

from gordie.data.models import Medium
from gordie.scheduled.jobs import register_scheduled_jobs
from gordie.server.routes.oauth_routes import register_oauth_routes


async def test_yahoo_callback_saves_tokens_for_existing_email_identity(monkeypatch) -> None:
    monkeypatch.setenv("YAHOO_CLIENT_ID", "test-client")
    monkeypatch.setenv("YAHOO_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("OAUTH_BASE_URL", "https://gordie.example.com")

    app = Quart(__name__)
    register_oauth_routes(app)
    user_id = UUID("7dc8bd5f-7d86-47c8-9a7a-3ad6c97c4e58")
    pending_repo = MagicMock()
    pending_repo.get.return_value = (
        "pending-id",
        "nonce",
        "email",
        "source@example.com",
        "thread-id",
        None,
    )
    user_repo = MagicMock()
    user_repo.get_by_identity.side_effect = [None, (user_id,)]

    with (
        patch(
            "gordie.data.pending_oauth_repository.PendingOAuthRepository", return_value=pending_repo
        ),
        patch("gordie.data.user_repository.UserRepository", return_value=user_repo),
        patch(
            "gordie.server.oauth.exchange_code",
            return_value={"access_token": "test-access", "refresh_token": "test-refresh"},
        ),
        patch("gordie.server.oauth.get_yahoo_email", return_value="yahoo@example.com"),
        patch("gordie.data.yahoo_token_repository.save_tokens_by_user_id") as save_tokens,
    ):
        response = await app.test_client().get("/callback?code=test-code&state=pending-id")

    assert response.status_code == 200
    assert "Authentication Successful" in cast(str, await response.get_data(as_text=True))
    user_repo.link_identity.assert_called_once_with(
        user_id, Medium.EMAIL, "yahoo@example.com", "yahoo@example.com"
    )
    save_tokens.assert_called_once_with(
        str(user_id),
        "yahoo@example.com",
        {"access_token": "test-access", "refresh_token": "test-refresh"},
    )
    pending_repo.delete_by_id.assert_called_once_with("pending-id")


async def test_yahoo_callback_links_phone_identity_without_email_signup(monkeypatch) -> None:
    monkeypatch.setenv("YAHOO_CLIENT_ID", "test-client")
    monkeypatch.setenv("YAHOO_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("OAUTH_BASE_URL", "https://gordie.example.com")

    app = Quart(__name__)
    register_oauth_routes(app)
    user_id = UUID("7dc8bd5f-7d86-47c8-9a7a-3ad6c97c4e58")
    pending_repo = MagicMock()
    pending_repo.get.return_value = (
        "pending-id",
        "nonce",
        "phone",
        "+15551234567",
        "thread-id",
        None,
    )
    user_repo = MagicMock()
    user_repo.get_by_identity.side_effect = [None, (user_id,)]

    with (
        patch(
            "gordie.data.pending_oauth_repository.PendingOAuthRepository", return_value=pending_repo
        ),
        patch("gordie.data.user_repository.UserRepository", return_value=user_repo),
        patch("gordie.server.oauth.exchange_code", return_value={"access_token": "test-access"}),
        patch("gordie.server.oauth.get_yahoo_email", return_value="yahoo@example.com"),
        patch("gordie.data.yahoo_token_repository.save_tokens_by_user_id") as save_tokens,
    ):
        response = await app.test_client().get("/callback?code=test-code&state=pending-id")

    assert response.status_code == 200
    user_repo.get_by_identity.assert_any_call(Medium.PHONE, "+15551234567")
    user_repo.link_identity.assert_called_once_with(
        user_id, Medium.EMAIL, "yahoo@example.com", "yahoo@example.com"
    )
    save_tokens.assert_called_once_with(
        str(user_id), "yahoo@example.com", {"access_token": "test-access"}
    )


async def test_yahoo_callback_rejects_phone_identity_conflict(monkeypatch) -> None:
    monkeypatch.setenv("YAHOO_CLIENT_ID", "test-client")
    monkeypatch.setenv("YAHOO_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("OAUTH_BASE_URL", "https://gordie.example.com")

    app = Quart(__name__)
    register_oauth_routes(app)
    pending_repo = MagicMock()
    pending_repo.get.return_value = (
        "pending-id",
        "nonce",
        "phone",
        "+15551234567",
        "thread-id",
        None,
    )
    user_repo = MagicMock()
    user_repo.get_by_identity.side_effect = [
        (UUID("7dc8bd5f-7d86-47c8-9a7a-3ad6c97c4e58"),),
        (UUID("db23f4b6-9b7e-4b4d-8f27-aae4b899bc9f"),),
    ]

    with (
        patch(
            "gordie.data.pending_oauth_repository.PendingOAuthRepository", return_value=pending_repo
        ),
        patch("gordie.data.user_repository.UserRepository", return_value=user_repo),
        patch("gordie.server.oauth.exchange_code", return_value={"access_token": "test-access"}),
        patch("gordie.server.oauth.get_yahoo_email", return_value="yahoo@example.com"),
        patch("gordie.data.yahoo_token_repository.save_tokens_by_user_id") as save_tokens,
    ):
        response = await app.test_client().get("/callback?code=test-code&state=pending-id")

    assert response.status_code == 409
    user_repo.merge_users.assert_not_called()
    save_tokens.assert_not_called()


async def test_retired_channel_routes_are_absent() -> None:
    from gordie import create_app
    from gordie.integrations.defaults import default_plugins

    app = create_app(default_plugins(), openrouter_api_key="test-key", model="openai/gpt-4o-mini")
    client = app.test_client()

    for path in ("/api/signup", "/email/webhook", "/sms/webhook", "/discord/interactions"):
        response = await client.post(path)
        assert response.status_code == 404

    response = await client.get("/health")
    assert response.status_code == 200


def test_scheduler_keeps_stats_and_oauth_cleanup_without_delivery() -> None:
    scheduler = BackgroundScheduler()

    register_scheduled_jobs(scheduler)

    assert {job.id for job in scheduler.get_jobs()} == {
        "refresh_stats_db",
        "cleanup_pending_oauth",
    }
