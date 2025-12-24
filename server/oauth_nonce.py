"""OAuth nonce management utilities."""

from client.duck_db_client import get_platform_db_connection


def get_oauth_nonce(user_email: str) -> str | None:
    """
    Retrieve stored OAuth nonce for a user.

    Args:
        user_email: Email address of the user

    Returns:
        The nonce string if found, None otherwise
    """
    conn = get_platform_db_connection()
    try:
        result = conn.execute(
            """
            SELECT nonce FROM oauth_nonces WHERE user_email = ?
        """,
            (user_email,),
        ).fetchone()

        return result[0] if result else None
    finally:
        conn.close()


def get_oauth_nonce_and_thread(user_email: str) -> tuple[str, str] | None:
    """
    Retrieve stored OAuth nonce and thread_id for a user.

    Args:
        user_email: Email address of the user

    Returns:
        Tuple of (nonce, thread_id) if found, None otherwise
    """
    conn = get_platform_db_connection()
    try:
        result = conn.execute(
            """
            SELECT nonce, thread_id FROM oauth_nonces WHERE user_email = ?
        """,
            (user_email,),
        ).fetchone()

        return (result[0], result[1]) if result else None
    finally:
        conn.close()


def delete_oauth_nonce(user_email: str) -> None:
    """
    Delete OAuth nonce after use.

    Args:
        user_email: Email address of the user
    """
    conn = get_platform_db_connection()
    try:
        _ = conn.execute(
            """
            DELETE FROM oauth_nonces WHERE user_email = ?
        """,
            (user_email,),
        )
        _ = conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
