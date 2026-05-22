"""Repository class for Yahoo OAuth token records."""

from sqlalchemy import text
from sqlalchemy.orm import Session

from data.models import Medium
from data.repository import DatabaseRow, Repository
from data.user_repository import UserRepository


class YahooTokenRepository(Repository):
    """Repository for managing Yahoo OAuth token records."""

    def __init__(self, session: Session | None = None) -> None:
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
        user_id = UserRepository(self.session).resolve_user_id(Medium.EMAIL, user_email, user_email)
        self.upsert(
            ["user_id"],
            user_id=user_id,
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
        return self.session.execute(
            text(
                """
                SELECT
                    ui.external_id AS user_email,
                    yt.yahoo_email,
                    yt.access_token,
                    yt.refresh_token,
                    yt.token_time,
                    yt.token_type,
                    yt.updated_at,
                    yt.created_at
                FROM yahoo_tokens yt
                JOIN user_identities ui
                    ON ui.user_id = yt.user_id
                    AND ui.medium = :medium
                WHERE ui.external_id = :user_email
                """
            ),
            {"medium": Medium.EMAIL.value, "user_email": user_email},
        ).fetchone()


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
