from client.DuckDbClient import get_platform_db_connection

def get_user(email):
    conn = get_platform_db_connection()

    result = conn.execute("SELECT * FROM users WHERE email = ?", [email]).fetchone()

    if result:
        return result
    else:
        return None
