from client.duck_db_client import get_platform_db_connection


def add_user(email):
    """
    Add a new user to the database.

    Args:
        email: User's primary email address
        yahoo_email: User's Yahoo email address (optional, if different from primary email)
    """
    conn = get_platform_db_connection()

    conn.execute("INSERT INTO users (email) VALUES (?)", [email])

    conn.commit()
    conn.close()
