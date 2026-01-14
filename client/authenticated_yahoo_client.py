"""
Yahoo OAuth token management with better error handling for CI/CD environments.

This module provides robust token management including:
- JSON-based token storage (cleaner than individual env vars)
- Automatic token refresh with error handling
- Clear error messages when re-authentication is needed
"""

import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from yfpy.query import YahooFantasySportsQuery

from client.duck_db_client import get_platform_db_connection
from module.logger import get_logger

load_dotenv()
logger = get_logger(__name__)


class AuthenticatedYahooClient:
    """Yahoo Fantasy Sports authenticated client with robust token handling."""

    def __init__(
        self,
        user_email: str,
        league_id: int | None = None,
        access_token_json: str | None = None,
    ):
        """
        Initialize Yahoo Fantasy Sports client with robust token handling.

        Args:
            league_id: Yahoo Fantasy League ID (optional for league-specific queries)
            access_token_json: JSON string containing all token data (defaults to db lookup)
            user_email: User's Yahoo email (Used to fetch tokens from database)

        Raises:
            ValueError: If required credentials are missing or no auth token found for user
            RuntimeError: If token refresh fails
        """
        self.user_email = user_email
        self.league_id = league_id
        self.consumer_key = os.getenv("YAHOO_CLIENT_ID")
        self.consumer_secret = os.getenv("YAHOO_CLIENT_SECRET")

        # Validate required credentials (league_id is now optional)
        missing = [
            name
            for name, value in [
                ("YAHOO_CLIENT_ID", self.consumer_key),
                ("YAHOO_CLIENT_SECRET", self.consumer_secret),
            ]
            if not value
        ]
        if missing:
            raise ValueError(f"Missing required credentials: {', '.join(missing)}")

        self.access_token_json = self._fetch_tokens_from_db(user_email)
        self._query = None

    def _fetch_tokens_from_db(self, user_email: str) -> str:
        """
        Fetch Yahoo OAuth tokens from database for the given user email.

        Args:
            user_email: User's email address

        Returns:
            JSON string containing token data

        Raises:
            ValueError: If no auth token found for the user
        """
        conn = get_platform_db_connection()
        try:
            result = conn.execute(
                """
                SELECT access_token, refresh_token, token_time, token_type
                FROM yahoo_tokens
                WHERE user_email = ?
            """,
                [user_email],
            ).fetchone()

            if not result:
                raise ValueError(
                    f"No auth token found for user: {user_email}. "
                    "User must authenticate first using the OAuth flow."
                )

            access_token, refresh_token, token_time, token_type = result

            # Convert timestamp to Unix epoch float
            token_time_float = (
                token_time.timestamp() if hasattr(token_time, "timestamp") else float(token_time)
            )

            token_data = {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_time": token_time_float,
                "token_type": token_type,
            }

            logger.info(f"Loaded OAuth tokens from database for user: {user_email}")
            return json.dumps(token_data)

        finally:
            conn.close()

    @property
    def query(self) -> YahooFantasySportsQuery:
        """
        Get or create the Yahoo Fantasy Sports Query object.

        Returns:
            Configured YahooFantasySportsQuery object

        Raises:
            RuntimeError: If token creation or refresh fails
        """
        if self._query is None:
            self._query = self._create_query()
        return self._query

    def _create_query(self) -> YahooFantasySportsQuery:
        """
        Create Yahoo Fantasy Sports Query with token handling.

        Returns:
            Configured YahooFantasySportsQuery object

        Raises:
            RuntimeError: If token creation fails
        """
        if self.access_token_json:
            try:
                token_data = json.loads(self.access_token_json.strip())

                # Check token age and log if expired
                if token_data.get("token_time"):
                    token_age_hours = (datetime.now().timestamp() - token_data["token_time"]) / 3600
                    if token_age_hours > 1:
                        logger.warning(
                            f"Access token expired ({token_age_hours:.1f}h old, will auto-refresh)"
                        )

                return self._create_query_with_token(token_data)
            except json.JSONDecodeError as e:
                raise RuntimeError(
                    f"Invalid YAHOO_ACCESS_TOKEN_JSON format: {e}. "
                    "Ensure it's valid single-line JSON with proper escaping."
                ) from e

        # No token found - requires interactive authentication
        logger.warning(
            "No token data found - starting OAuth flow (requires interactive authentication)"
        )

        # Use a dummy league_id if none provided (needed for user league queries)
        query_league_id = self.league_id or 0

        query = YahooFantasySportsQuery(
            league_id=str(query_league_id),
            game_code="nhl",
            game_id=None,
            yahoo_consumer_key=self.consumer_key,
            yahoo_consumer_secret=self.consumer_secret,
            env_file_location=Path("."),
            save_token_data_to_env_file=False,  # Disabled - we save to DB instead
        )

        # Hook into the OAuth token refresh to save updated tokens to database
        if query.oauth:
            original_refresh = query.oauth.refresh_access_token

            def refresh_with_db_save(*args, **kwargs):
                # Call original refresh
                result = original_refresh(*args, **kwargs)
                # Save refreshed tokens to database
                logger.info("Token refreshed - saving to database")
                self._save_tokens_to_db(query)
                return result

            query.oauth.refresh_access_token = refresh_with_db_save

        return query

    def _save_tokens_to_db(self, query: YahooFantasySportsQuery) -> None:
        """
        Save current tokens from the query object to the database.

        Args:
            query: YahooFantasySportsQuery instance with current tokens
        """
        try:
            # Extract token data from the query's oauth session
            oauth = query.oauth
            if oauth and hasattr(oauth, "access_token"):
                token_time = datetime.now()

                conn = get_platform_db_connection()
                try:
                    conn.execute(
                        """
                        UPDATE yahoo_tokens
                        SET access_token = ?,
                            refresh_token = ?,
                            token_time = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE user_email = ?
                        """,
                        (
                            oauth.access_token,
                            oauth.refresh_token,
                            token_time,
                            self.user_email,
                        ),
                    )
                    conn.commit()
                    logger.info(f"Updated refreshed tokens in database for user: {self.user_email}")
                finally:
                    conn.close()
        except Exception as e:
            logger.error(f"Failed to save refreshed tokens to database: {e}")
            # Don't raise - token refresh succeeded, DB update is secondary

    def _create_query_with_token(self, token_data: dict[str, str]) -> YahooFantasySportsQuery:
        """
        Create YahooFantasySportsQuery with existing token data.

        Args:
            token_data: Dictionary containing token information

        Returns:
            Configured YahooFantasySportsQuery object with token refresh hook

        Raises:
            RuntimeError: If query creation fails
        """
        try:
            full_token_data = {
                **token_data,
                "consumer_key": self.consumer_key,
                "consumer_secret": self.consumer_secret,
                "guid": None,
            }

            # Use a dummy league_id if none provided (needed for user league queries)
            query_league_id = self.league_id or 0

            query = YahooFantasySportsQuery(
                league_id=str(query_league_id),
                game_code="nhl",
                game_id=None,
                yahoo_consumer_key=self.consumer_key,
                yahoo_consumer_secret=self.consumer_secret,
                yahoo_access_token_json=full_token_data,
                env_file_location=Path("."),
                save_token_data_to_env_file=False,  # Disabled - we save to DB instead
            )

            # Hook into the OAuth token refresh to save updated tokens to database
            if query.oauth:
                original_refresh = query.oauth.refresh_access_token

                def refresh_with_db_save(*args, **kwargs):
                    # Call original refresh
                    result = original_refresh(*args, **kwargs)
                    # Save refreshed tokens to database
                    logger.info("Token refreshed - saving to database")
                    self._save_tokens_to_db(query)
                    return result

                query.oauth.refresh_access_token = refresh_with_db_save

            return query

        except Exception as e:
            raise RuntimeError(
                f"Failed to create Yahoo query: {e}. "
                "Token may be expired or invalid. Re-authenticate and update secrets."
            ) from e

    @staticmethod
    def export_tokens_to_json() -> str | None:
        """
        Export current token data from .env to JSON format for GitHub secrets.

        Returns:
            JSON string containing all token data, or None if tokens not found
        """
        load_dotenv()

        access_token = os.getenv("YAHOO_ACCESS_TOKEN")
        refresh_token = os.getenv("YAHOO_REFRESH_TOKEN")
        token_time = os.getenv("YAHOO_TOKEN_TIME")
        token_type = os.getenv("YAHOO_TOKEN_TYPE", "bearer")

        if not access_token or not refresh_token:
            logger.error("Token data not found in .env file. Run authentication flow first.")
            return None

        token_data = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_time": float(token_time) if token_time else None,
            "token_type": token_type,
        }

        json_str = json.dumps(token_data)

        logger.info("GitHub Secret: YAHOO_ACCESS_TOKEN_JSON")
        logger.info(json_str)
        logger.info("\nAdd to GitHub → Settings → Secrets → New repository secret")

        return json_str

    @staticmethod
    def check_token_health() -> dict[str, str | bool | float]:
        """
        Check the health of current OAuth tokens.

        Returns:
            Dictionary with token status information
        """
        load_dotenv()

        access_token = os.getenv("YAHOO_ACCESS_TOKEN")
        refresh_token = os.getenv("YAHOO_REFRESH_TOKEN")
        token_time_str = os.getenv("YAHOO_TOKEN_TIME")

        if not access_token or not refresh_token:
            return {
                "status": "missing",
                "message": "No token data found",
                "needs_reauth": True,
            }

        token_time = float(token_time_str) if token_time_str else 0
        token_age_hours = (datetime.now().timestamp() - token_time) / 3600

        if token_age_hours > 1:
            return {
                "status": "expired",
                "message": f"Token expired {token_age_hours:.1f}h ago (will auto-refresh)",
                "needs_reauth": False,
                "token_age_hours": token_age_hours,
                "has_refresh_token": True,
            }

        return {
            "status": "valid",
            "message": f"Token valid (expires in {1 - token_age_hours:.1f}h)",
            "needs_reauth": False,
            "token_age_hours": token_age_hours,
            "has_refresh_token": True,
        }
