"""OAuth nonce management utilities."""

from sqlalchemy import text

from data.database import get_session


def get_oauth_nonce(user_email: str) -> str | None:
    """
    Retrieve stored OAuth nonce for a user.

    Args:
        user_email: Email address of the user

    Returns:
        The nonce string if found, None otherwise
    """
    session = get_session()
    try:
        result = session.execute(
            text("SELECT nonce FROM oauth_nonces WHERE user_email = :user_email"),
            {"user_email": user_email},
        ).fetchone()

        return result[0] if result else None
    finally:
        session.close()


def get_oauth_nonce_and_thread(user_email: str) -> tuple[str, str] | None:
    """
    Retrieve stored OAuth nonce and thread_id for a user.

    Args:
        user_email: Email address of the user

    Returns:
        Tuple of (nonce, thread_id) if found, None otherwise
    """
    session = get_session()
    try:
        result = session.execute(
            text(
                "SELECT nonce, thread_id FROM oauth_nonces WHERE user_email = :user_email"
            ),
            {"user_email": user_email},
        ).fetchone()

        return (result[0], result[1]) if result else None
    finally:
        session.close()


def delete_oauth_nonce(user_email: str) -> None:
    """
    Delete OAuth nonce after use.

    Args:
        user_email: Email address of the user
    """
    session = get_session()
    try:
        session.execute(
            text("DELETE FROM oauth_nonces WHERE user_email = :user_email"),
            {"user_email": user_email},
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
