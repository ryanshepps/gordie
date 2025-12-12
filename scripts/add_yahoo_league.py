from client.DuckDbClient import get_platform_db_connection


def add_yahoo_league(league_id: int, game_key: str, league_name: str, league_type: str, league_settings: str):
    """
    Add a Yahoo Fantasy league to the database.

    Args:
        league_id: Yahoo Fantasy league ID (e.g., "nhl.l.12345")
        game_key: Yahoo Fantasy game key (e.g., "nhl")
        league_name: Name of the league
        league_type: Type of league (e.g., "nhl", "nfl")
        league_settings: JSON string of league settings
    """
    conn = get_platform_db_connection()

    conn.execute(
        "INSERT INTO yahoo_leagues (league_id, game_key, league_name, league_type, league_settings) VALUES (?, ?, ?, ?, ?)",
        [league_id, game_key, league_name, league_type, league_settings]
    )

    conn.commit()
    conn.close()
