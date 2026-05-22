"""Integration tests for SMS webhook endpoint."""

import json
import time
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from server.routes.sms_routes import _rate_limit_store


@pytest.fixture(autouse=True)
def clear_rate_limits():
    """Clear rate limit store between tests."""
    _rate_limit_store.clear()
    yield
    _rate_limit_store.clear()


VALID_TOKEN = "test-webhook-token"


@pytest.fixture
def sms_env(monkeypatch):
    """Set required environment variables for SMS webhook tests."""
    monkeypatch.setenv("SINCH_WEBHOOK_TOKEN", VALID_TOKEN)
    monkeypatch.setenv("SINCH_SERVICE_PLAN_ID", "test-plan")
    monkeypatch.setenv("SINCH_API_TOKEN", "test-token")
    monkeypatch.setenv("SINCH_FROM_NUMBER", "+15550001111")


@pytest.fixture
def app(sms_env):
    """Create a Quart test app with SMS routes registered."""
    from quart import Quart

    from server.routes.sms_routes import register_sms_routes

    app = Quart(__name__)
    register_sms_routes(app)
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


def _mock_processed_repo(claimed: bool = True) -> MagicMock:
    mock_repo = MagicMock()
    mock_repo.claim.return_value = claimed
    return mock_repo


class TestSmsWebhook:
    async def test_valid_sms_returns_200(self, client):
        """Valid SMS webhook triggers agent processing and returns 200."""
        payload = {"from": "+15559876543", "body": "Who should I start?", "id": "sinch-msg-1"}
        body = json.dumps(payload).encode()

        mock_processed_repo = _mock_processed_repo()
        mock_user_repo = MagicMock()
        mock_user_repo.is_sms_opted_out.return_value = False
        user_id = UUID("7dc8bd5f-7d86-47c8-9a7a-3ad6c97c4e58")
        mock_user_repo.get_by_identity.return_value = (user_id, "created")
        mock_user_repo.get_identity_external_id.return_value = "user@test.com"

        mock_thread_info = MagicMock(
            thread_id="8ec8bd5f-7d86-47c8-9a7a-3ad6c97c4e58", is_new_thread=True
        )
        mock_thread_repo = MagicMock()
        mock_thread_repo.resolve.return_value = mock_thread_info

        with (
            patch(
                "server.routes.sms_routes.ProcessedInboundMessageRepository",
                return_value=mock_processed_repo,
            ),
            patch(
                "server.routes.sms_routes.UserRepository",
                return_value=mock_user_repo,
            ),
            patch("server.routes.sms_routes.ThreadRepository", return_value=mock_thread_repo),
            patch("server.routes.sms_routes.threading") as mock_threading,
        ):
            response = await client.post(
                f"/sms/webhook?auth_token={VALID_TOKEN}",
                data=body,
                headers={"Content-Type": "application/json"},
            )

        assert response.status_code == 200
        data = await response.get_json()
        assert data["status"] == "received"
        mock_threading.Thread.assert_called_once()

    async def test_invalid_token_returns_403(self, client):
        """Invalid auth token is rejected with 403."""
        payload = {"from": "+15559876543", "body": "Hello", "id": "sinch-msg-2"}
        body = json.dumps(payload).encode()

        response = await client.post(
            "/sms/webhook?auth_token=wrong-token",
            data=body,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 403

    async def test_duplicate_message_returns_200(self, client):
        """Duplicate Sinch message IDs are skipped with 200."""
        payload = {"from": "+15559876543", "body": "Hello", "id": "sinch-msg-dup"}
        body = json.dumps(payload).encode()

        mock_processed_repo = _mock_processed_repo(claimed=False)

        with patch(
            "server.routes.sms_routes.ProcessedInboundMessageRepository",
            return_value=mock_processed_repo,
        ):
            response = await client.post(
                f"/sms/webhook?auth_token={VALID_TOKEN}",
                data=body,
                headers={"Content-Type": "application/json"},
            )

        assert response.status_code == 200
        data = await response.get_json()
        assert data["status"] == "duplicate"

    async def test_opt_out_keyword_sends_confirmation(self, client):
        """Sending STOP triggers opt-out and confirmation SMS."""
        payload = {"from": "+15559876543", "body": "STOP", "id": "sinch-msg-stop"}
        body = json.dumps(payload).encode()

        mock_processed_repo = _mock_processed_repo()
        mock_user_repo = MagicMock()
        mock_sms_instance = MagicMock()

        with (
            patch(
                "server.routes.sms_routes.ProcessedInboundMessageRepository",
                return_value=mock_processed_repo,
            ),
            patch(
                "server.routes.sms_routes.UserRepository",
                return_value=mock_user_repo,
            ),
            patch(
                "server.routes.sms_routes.SmsService",
                return_value=mock_sms_instance,
            ),
        ):
            response = await client.post(
                f"/sms/webhook?auth_token={VALID_TOKEN}",
                data=body,
                headers={"Content-Type": "application/json"},
            )

        assert response.status_code == 200
        data = await response.get_json()
        assert data["status"] == "opt_out"
        mock_user_repo.set_sms_opt_out.assert_called_once_with("+15559876543", opted_out=True)
        mock_sms_instance.send_sms.assert_called_once()
        assert "unsubscribed" in mock_sms_instance.send_sms.call_args[0][1].lower()

    async def test_rate_limit_drops_excess_messages(self, client):
        """Excess messages from same phone are dropped after rate limit."""
        from server.routes.sms_routes import RATE_LIMIT_MAX

        _rate_limit_store["+15559876543"] = [time.time()] * RATE_LIMIT_MAX

        payload = {"from": "+15559876543", "body": "One more", "id": "sinch-msg-rate"}
        body = json.dumps(payload).encode()

        mock_processed_repo = _mock_processed_repo()

        with patch(
            "server.routes.sms_routes.ProcessedInboundMessageRepository",
            return_value=mock_processed_repo,
        ):
            response = await client.post(
                f"/sms/webhook?auth_token={VALID_TOKEN}",
                data=body,
                headers={"Content-Type": "application/json"},
            )

        assert response.status_code == 200
        data = await response.get_json()
        assert data["status"] == "rate_limited"

    async def test_unknown_phone_creates_pending_user(self, client):
        """Unknown phone number creates a pending_user record."""
        payload = {"from": "+15550009999", "body": "Hi", "id": "sinch-msg-new"}
        body = json.dumps(payload).encode()

        mock_processed_repo = _mock_processed_repo()
        mock_user_repo = MagicMock()
        mock_user_repo.is_sms_opted_out.return_value = False
        mock_user_repo.get_by_identity.return_value = None
        mock_user_repo.create_with_identity.return_value = UUID(
            "7dc8bd5f-7d86-47c8-9a7a-3ad6c97c4e58"
        )

        mock_pending_repo = MagicMock()
        mock_pending_repo.get_pending_user_by_phone.return_value = None

        mock_thread_info = MagicMock(
            thread_id="8ec8bd5f-7d86-47c8-9a7a-3ad6c97c4e58", is_new_thread=True
        )
        mock_thread_repo = MagicMock()
        mock_thread_repo.resolve.return_value = mock_thread_info

        with (
            patch(
                "server.routes.sms_routes.ProcessedInboundMessageRepository",
                return_value=mock_processed_repo,
            ),
            patch(
                "server.routes.sms_routes.UserRepository",
                return_value=mock_user_repo,
            ),
            patch(
                "server.routes.sms_routes.PendingUserRepository",
                return_value=mock_pending_repo,
            ),
            patch("server.routes.sms_routes.ThreadRepository", return_value=mock_thread_repo),
            patch("server.routes.sms_routes.threading"),
            patch("server.routes.sms_routes._generate_cold_start_oauth_link", return_value="url"),
            patch("server.routes.sms_routes.SmsService"),
        ):
            response = await client.post(
                f"/sms/webhook?auth_token={VALID_TOKEN}",
                data=body,
                headers={"Content-Type": "application/json"},
            )

        assert response.status_code == 200
        mock_pending_repo.add_pending_user.assert_called_once_with(phone_number="+15550009999")
