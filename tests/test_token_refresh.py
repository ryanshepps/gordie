"""Test token refresh and database persistence."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from client.authenticated_yahoo_client import AuthenticatedYahooClient


@pytest.fixture
def mock_db_connection():
    """Mock database connection."""
    conn = MagicMock()
    conn.execute.return_value = MagicMock()
    conn.commit.return_value = None
    conn.close.return_value = None
    return conn


@pytest.fixture
def mock_user_tokens():
    """Mock user tokens from database."""
    return {
        "access_token": "old_access_token",
        "refresh_token": "old_refresh_token",
        "token_time": datetime.now().timestamp() - 7200,  # 2 hours ago (expired)
        "token_type": "Bearer",
    }


def test_token_refresh_saves_to_database(mock_db_connection, mock_user_tokens, monkeypatch):
    """Test that token refresh triggers database save."""
    user_email = "test@example.com"

    # Set required environment variables
    monkeypatch.setenv("YAHOO_CLIENT_ID", "test_client_id")
    monkeypatch.setenv("YAHOO_CLIENT_SECRET", "test_client_secret")

    with (
        patch("client.authenticated_yahoo_client.get_platform_db_connection") as mock_get_conn,
        patch("client.authenticated_yahoo_client.YahooFantasySportsQuery") as mock_query_class,
    ):
        # Setup mocks
        mock_get_conn.return_value = mock_db_connection

        # Mock the query instance with oauth
        mock_query = MagicMock()
        mock_oauth = MagicMock()
        mock_oauth.access_token = "new_access_token"
        mock_oauth.refresh_token = "new_refresh_token"
        mock_oauth.refresh_access_token = MagicMock(return_value={"token_type": "Bearer"})
        mock_query.oauth = mock_oauth
        mock_query_class.return_value = mock_query

        # Setup database to return tokens on first call
        mock_db_connection.execute.return_value.fetchone.return_value = (
            mock_user_tokens["access_token"],
            mock_user_tokens["refresh_token"],
            mock_user_tokens["token_time"],
            mock_user_tokens["token_type"],
        )

        # Create client (this should wrap the refresh method)
        client = AuthenticatedYahooClient(user_email=user_email)
        query = client.query

        # Verify the refresh method was wrapped
        assert query.oauth is not None
        assert hasattr(query.oauth, "refresh_access_token")

        # Simulate token refresh by calling the wrapped method
        query.oauth.refresh_access_token()

        # Verify database UPDATE was called with new tokens
        update_calls = [
            call for call in mock_db_connection.execute.call_args_list if "UPDATE" in str(call)
        ]
        assert len(update_calls) > 0, "Database UPDATE should be called after token refresh"

        # Verify commit was called
        assert mock_db_connection.commit.called


def test_save_tokens_to_db_handles_missing_oauth(mock_db_connection):
    """Test that _save_tokens_to_db handles queries without oauth gracefully."""
    user_email = "test@example.com"

    with patch("client.authenticated_yahoo_client.get_platform_db_connection") as mock_get_conn:
        mock_get_conn.return_value = mock_db_connection

        client = AuthenticatedYahooClient.__new__(AuthenticatedYahooClient)
        client.user_email = user_email

        # Create mock query without oauth
        mock_query = MagicMock()
        mock_query.oauth = None

        # Should not raise an error
        client._save_tokens_to_db(mock_query)

        # Should not call database update
        assert not mock_db_connection.execute.called
