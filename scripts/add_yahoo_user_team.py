from client.DuckDbClient import get_platform_db_connection


def add_yahoo_user_team(league_id: int, team_id: int, user_email: str, team_name: str):
    """
    Add a user's Yahoo Fantasy team to the database.

    Args:
        league_id: Yahoo Fantasy league ID (e.g., "12345")
        team_id: Yahoo Fantasy team ID
        user_email: User's email address
        team_name: Name of the team
    """
    conn = get_platform_db_connection()

    conn.execute(
        "INSERT INTO yahoo_user_teams (league_id, team_id, user_email, team_name) VALUES (?, ?, ?, ?)",
        [league_id, team_id, user_email, team_name]
    )

    conn.commit()
    conn.close()
