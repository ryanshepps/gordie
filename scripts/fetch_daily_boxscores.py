#!/usr/bin/env python3
"""
Fetch NHL box scores for a given date and insert into DuckDB.

This script fetches all games for a specified date, retrieves box score data
for all players, and efficiently inserts it into the player_stats table using
DuckDB's DataFrame ingestion capabilities.
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from nhlpy import NHLClient

sys.path.append(str(Path(__file__).parent.parent))

from data.schemas import get_db_connection, create_player_stats_table
from module.logger import get_logger

logger = get_logger(__name__, level=logging.INFO)


def fetch_boxscore_data(date_str: str) -> list[dict]:
    """
    Fetch box score data for all players from all games on a given date.

    Args:
        date_str: Date in YYYY-MM-DD format

    Returns:
        List of player stat dictionaries
    """
    client = NHLClient()

    logger.info(f"Fetching games for {date_str}")
    schedule = client.schedule.daily_schedule(date_str)

    if not schedule or 'games' not in schedule:
        logger.warning(f"No games found for {date_str}")
        return []

    games = schedule['games']

    if not games:
        logger.warning(f"No games found for {date_str}")
        return []

    logger.info(f"Found {len(games)} games on {date_str}")

    all_player_stats = []

    for game in games:
        game_id = game['id']
        logger.info(f"Fetching boxscore for game {game_id}")

        try:
            boxscore = client.game_center.boxscore(game_id)

            if not boxscore or 'playerByGameStats' not in boxscore:
                logger.warning(f"No boxscore data for game {game_id}")
                continue

            player_stats = boxscore['playerByGameStats']

            # Process away team players
            if 'awayTeam' in player_stats:
                for position in ['forwards', 'defense']:
                    if position in player_stats['awayTeam']:
                        for player in player_stats['awayTeam'][position]:
                            player_dict = extract_player_stats(player, game_id, date_str)
                            if player_dict:
                                all_player_stats.append(player_dict)

            # Process home team players
            if 'homeTeam' in player_stats:
                for position in ['forwards', 'defense']:
                    if position in player_stats['homeTeam']:
                        for player in player_stats['homeTeam'][position]:
                            player_dict = extract_player_stats(player, game_id, date_str)
                            if player_dict:
                                all_player_stats.append(player_dict)

        except Exception as e:
            logger.error(f"Error fetching boxscore for game {game_id}: {e}")
            continue

    logger.info(f"Fetched stats for {len(all_player_stats)} players")
    return all_player_stats


def extract_player_stats(player: dict, game_id: int, game_date: str) -> dict | None:
    """
    Extract relevant stats from a player boxscore dictionary.

    Args:
        player: Player boxscore dictionary from nhl-api-py
        game_id: NHL API game ID
        game_date: Game date in YYYY-MM-DD format

    Returns:
        Dictionary with player stats matching the database schema
    """
    try:
        return {
            'nhl_api_player_id': player.get('playerId'),
            'nhl_api_game_id': game_id,
            'game_date': game_date,
            'goals': player.get('goals', 0),
            'assists': player.get('assists', 0),
            'points': player.get('points', 0),
            'plus_minus': player.get('plusMinus', 0),
            'pim': player.get('pim', 0),
            'hits': player.get('hits', 0),
            'power_play_goals': player.get('powerPlayGoals', 0),
            'sog': player.get('sog', 0),
            'faceoff_winning_pctg': player.get('faceoffWinningPctg', 0.0),
            'toi': player.get('toi', '00:00'),
            'blocked_shots': player.get('blockedShots', 0),
            'shifts': player.get('shifts', 0),
            'giveaways': player.get('giveaways', 0),
            'takeaways': player.get('takeaways', 0)
        }
    except (KeyError, TypeError) as e:
        logger.warning(f"Error extracting stats for player: {e}")
        return None


def insert_player_stats(conn, player_stats: list[dict]) -> None:
    """
    Insert player stats into DuckDB using efficient DataFrame ingestion.

    Uses DuckDB's ability to directly query DataFrames for optimal performance.
    See: https://duckdb.org/docs/stable/clients/python/data_ingestion

    Args:
        conn: DuckDB connection
        player_stats: List of player stat dictionaries
    """
    if not player_stats:
        logger.warning("No player stats to insert")
        return

    # Convert to DataFrame for efficient batch insertion
    df = pd.DataFrame(player_stats)

    logger.info(f"Inserting {len(df)} player records")

    # DuckDB can directly query the DataFrame variable
    # Using INSERT OR REPLACE to handle PRIMARY KEY conflicts
    conn.execute("""
        INSERT OR REPLACE INTO player_stats
        SELECT
            nhl_api_player_id,
            nhl_api_game_id,
            game_date,
            goals,
            assists,
            points,
            plus_minus,
            pim,
            hits,
            power_play_goals,
            sog,
            faceoff_winning_pctg,
            toi,
            blocked_shots,
            shifts,
            giveaways,
            takeaways
        FROM df
    """)

    logger.info(f"Successfully inserted {len(df)} player records")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Fetch NHL box scores for a date and insert into DuckDB'
    )
    parser.add_argument(
        'date',
        type=str,
        help='Date in YYYY-MM-DD format (e.g., 2025-12-06)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Validate date format
    try:
        datetime.strptime(args.date, '%Y-%m-%d')
    except ValueError:
        logger.error(f"Invalid date format: {args.date}. Use YYYY-MM-DD")
        sys.exit(1)

    # Connect to database and ensure table exists
    conn = get_db_connection()
    create_player_stats_table(conn)

    try:
        # Fetch box score data
        player_stats = fetch_boxscore_data(args.date)

        # Insert into database
        insert_player_stats(conn, player_stats)

        logger.info("Box score data ingestion complete")

    except Exception as e:
        logger.error(f"Error during execution: {e}")
        sys.exit(1)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
