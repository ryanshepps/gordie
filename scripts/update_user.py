from client.duck_db_client import get_platform_db_connection


def update_user(email):
    """
    Update an existing user in the database.

    Args:
        email: User's primary email address (used to identify the user)
    """
    conn = get_platform_db_connection()

    conn.execute("UPDATE users SET email = ? WHERE email = ?", [email, email])

    conn.commit()
    conn.close()
