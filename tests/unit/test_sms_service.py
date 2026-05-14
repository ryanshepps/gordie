"""Tests for Sinch SMS service."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from server.sms_service import SmsService


@pytest.fixture
def sms_env(monkeypatch):
    """Set required Sinch environment variables."""
    monkeypatch.setenv("SINCH_SERVICE_PLAN_ID", "test-plan-id")
    monkeypatch.setenv("SINCH_API_TOKEN", "test-api-token")
    monkeypatch.setenv("SINCH_FROM_NUMBER", "+15551234567")


class TestSmsService:
    def test_successful_send(self, sms_env):
        """SMS sends successfully and returns batch_id."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "batch-123"}

        with patch("server.sms_service.requests.post", return_value=mock_response) as mock_post:
            service = SmsService()
            result = service.send_sms("+15559876543", "Hello!")

        assert result.success is True
        assert result.batch_id == "batch-123"
        assert result.error is None

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs.kwargs["json"]["to"] == ["+15559876543"]
        assert call_kwargs.kwargs["json"]["body"] == "Hello!"

    def test_4xx_does_not_retry(self, sms_env):
        """4xx errors return failure immediately without retry."""
        mock_response = MagicMock()
        mock_response.status_code = 422
        mock_response.text = "Invalid phone number"
        mock_response.raise_for_status.side_effect = None

        with patch("server.sms_service.requests.post", return_value=mock_response) as mock_post:
            service = SmsService()
            result = service.send_sms("+15559876543", "Hello!")

        assert result.success is False
        assert result.error is not None and "Client error: 422" in result.error
        mock_post.assert_called_once()

    def test_5xx_retries_once(self, sms_env):
        """5xx errors trigger one retry then succeed."""
        error_response = MagicMock()
        error_response.status_code = 500
        error_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=error_response
        )

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {"id": "batch-456"}

        with (
            patch(
                "server.sms_service.requests.post",
                side_effect=[error_response, success_response],
            ) as mock_post,
            patch("server.sms_service.time.sleep"),
        ):
            service = SmsService()
            result = service.send_sms("+15559876543", "Hello!")

        assert result.success is True
        assert result.batch_id == "batch-456"
        assert mock_post.call_count == 2

    def test_timeout_retries_once(self, sms_env):
        """Timeouts trigger one retry."""
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {"id": "batch-789"}

        with (
            patch(
                "server.sms_service.requests.post",
                side_effect=[requests.exceptions.Timeout(), success_response],
            ) as mock_post,
            patch("server.sms_service.time.sleep"),
        ):
            service = SmsService()
            result = service.send_sms("+15559876543", "Hello!")

        assert result.success is True
        assert mock_post.call_count == 2

    def test_missing_env_boots_disabled(self, monkeypatch):
        """Missing env vars leave the service in a disabled state, not raising."""
        monkeypatch.delenv("SINCH_SERVICE_PLAN_ID", raising=False)
        monkeypatch.delenv("SINCH_API_TOKEN", raising=False)
        monkeypatch.delenv("SINCH_FROM_NUMBER", raising=False)

        service = SmsService()
        assert service.enabled is False

        result = service.send_sms("+15551234567", "test")
        assert result.success is False
        assert result.error == "sms_disabled"
