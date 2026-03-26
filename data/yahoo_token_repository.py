"""Repository class for Yahoo OAuth token records."""

from sqlalchemy import text
from sqlalchemy.orm import Session

from data.database import get_session
from data.repository import DatabaseRow, Repository


class YahooTokenRepository(Repository):
    """Repository for managing Yahoo OAuth token records."""

    def __init__(self, session: Session | None = None):
        """Initialize Yahoo token repository.

        Args:
            session: Optional database session. If not provided, creates a new one.
        """
        super().__init__("yahoo_tokens", session)

    def save_token(
        self,
        user_email: str,
        yahoo_email: str,
        access_token: str,
        refresh_token: str,
        token_time: str,
        token_type: str = "Bearer",
    ) -> None:
        """Save or update Yahoo OAuth tokens for a user.

        Args:
            user_email: User's email address
            yahoo_email: Yahoo email address
            access_token: OAuth access token
            refresh_token: OAuth refresh token
            token_time: Timestamp when token was issued
            token_type: Token type (default: "Bearer")
        """
        self.upsert(
            ["user_email"],
            user_email=user_email,
            yahoo_email=yahoo_email,
            access_token=access_token,
            refresh_token=refresh_token,
            token_time=token_time,
            token_type=token_type,
        )

    def get_token(self, user_email: str) -> DatabaseRow | None:
        """Get OAuth tokens for a user.

        Args:
            user_email: User's email address

        Returns:
            Token record or None if not found
        """
        return self.get_by(user_email=user_email)


def load_tokens_from_db(user_email: str) -> dict[str, str] | None:
    """
    Load OAuth tokens from database.

    Args:
        user_email: Email address of the user

    Returns:
        dict with token data if found, None otherwise
    """
    repo = YahooTokenRepository()
    try:
        result = repo.get_token(user_email)
        if result:
            return {
                "access_token": result[2],  # access_token column
                "refresh_token": result[3],  # refresh_token column
                "token_time": result[4],  # token_time column
                "token_type": result[5],  # token_type column
            }
        return None
    finally:
        repo.close()


def save_tokens(user_email: str, yahoo_email: str, token_data: dict[str, str]) -> None:
    """Save OAuth tokens to database.

    Args:
        user_email: User's email address
        yahoo_email: Yahoo email address
        token_data: Dictionary containing access_token, refresh_token, token_time, token_type
    """
    # Ensure user exists first
    session = get_session()
    try:
        session.execute(
            text(
                """
                INSERT INTO users (email) VALUES (:email)
                ON CONFLICT (email) DO NOTHING
                """
            ),
            {"email": user_email},
        )
        session.commit()
    finally:
        session.close()

    # Save tokens using repository
    repo = YahooTokenRepository()
    try:
        repo.save_token(
            user_email=user_email,
            yahoo_email=yahoo_email,
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            token_time=token_data["token_time"],
            token_type=token_data.get("token_type", "Bearer"),
        )
    finally:
        repo.close()
