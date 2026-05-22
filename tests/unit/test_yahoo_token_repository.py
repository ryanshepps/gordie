"""Tests for Yahoo token persistence."""

from unittest.mock import MagicMock, patch

from data.yahoo_token_repository import save_tokens


def test_save_tokens_persists_token_without_creating_user() -> None:
    token_data = {
        "access_token": "access",
        "refresh_token": "refresh",
        "token_time": "2026-05-22T00:00:00",
        "token_type": "Bearer",
    }
    repo = MagicMock()

    with patch("data.yahoo_token_repository.YahooTokenRepository", return_value=repo):
        save_tokens("user@test.com", "yahoo@test.com", token_data)

    repo.save_token.assert_called_once_with(
        user_email="user@test.com",
        yahoo_email="yahoo@test.com",
        access_token="access",
        refresh_token="refresh",
        token_time="2026-05-22T00:00:00",
        token_type="Bearer",
    )
    repo.close.assert_called_once()
