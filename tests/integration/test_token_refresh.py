"""Test token refresh and database persistence."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from client.authenticated_yahoo_client import AuthenticatedYahooClient


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = MagicMock()
    session.execute.return_value = MagicMock()
    session.commit.return_value = None
    session.close.return_value = None
    return session


@pytest.fixture
def mock_user_tokens():
    """Mock user tokens from database."""
    return {
        "access_token": "old_access_token",
        "refresh_token": "old_refresh_token",
        "token_time": datetime.now().timestamp() - 7200,
        "token_type": "Bearer",
    }


def test_token_refresh_persists_to_database(mock_db_session, mock_user_tokens, monkeypatch):
    """After a token refresh, updated tokens are committed to the database."""
    user_email = "test@example.com"

    monkeypatch.setenv("YAHOO_CLIENT_ID", "test_client_id")
    monkeypatch.setenv("YAHOO_CLIENT_SECRET", "test_client_secret")

    with (
        patch("client.authenticated_yahoo_client.get_session") as mock_get_session,
        patch("client.authenticated_yahoo_client.YahooFantasySportsQuery") as mock_query_class,
    ):
        mock_get_session.return_value = mock_db_session

        mock_query = MagicMock()
        mock_oauth = MagicMock()
        mock_oauth.access_token = "new_access_token"
        mock_oauth.refresh_token = "new_refresh_token"
        mock_oauth.refresh_access_token = MagicMock(return_value={"token_type": "Bearer"})
        mock_query.oauth = mock_oauth
        mock_query_class.return_value = mock_query

        mock_db_session.execute.return_value.fetchone.return_value = (
            mock_user_tokens["access_token"],
            mock_user_tokens["refresh_token"],
            mock_user_tokens["token_time"],
            mock_user_tokens["token_type"],
        )

        client = AuthenticatedYahooClient(user_email=user_email)
        query = client.query

        execute_count_before_refresh = mock_db_session.execute.call_count

        query.oauth.refresh_access_token()

        assert mock_db_session.execute.call_count > execute_count_before_refresh, (
            "Database should receive a write after token refresh"
        )
        assert mock_db_session.commit.called, "Database commit should be called after token refresh"
