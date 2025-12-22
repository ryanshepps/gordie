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

import duckdb
import pandas as pd
from nhlpy import NHLClient

from client.duck_db_client import get_nhl_stats_db_connection
from data.schemas import create_nhl_player_game_stats_table
from module.logger import get_logger

logger = get_logger(__name__, level=logging.INFO)


def calculate_corsi_fenwick_from_playbyplay(client: NHLClient, game_id: int) -> pd.DataFrame:
    """
    Calculate Corsi and Fenwick stats from play-by-play data.

    Args:
        client: NHLClient instance
        game_id: NHL API game ID

    Returns:
        DataFrame with columns: nhl_api_player_id, corsi_for, fenwick_for, missed_shots
    """
    try:
        pbp = client.game_center.play_by_play(str(game_id))

        if not pbp or "plays" not in pbp:
            logger.warning(f"No play-by-play data for game {game_id}")
            return pd.DataFrame(
                {"nhl_api_player_id": [], "corsi_for": [], "fenwick_for": [], "missed_shots": []}
            )

        # Collect shot attempt events
        shot_attempts = []

        for play in pbp["plays"]:
            play_type = play.get("typeDescKey")

            if play_type in ["shot-on-goal", "missed-shot", "blocked-shot"]:
                details = play.get("details", {})
                player_id = details.get("shootingPlayerId") or details.get("playerId")

                if player_id:
                    shot_attempts.append(
                        {
                            "nhl_api_player_id": player_id,
                            "play_type": play_type,
                        }
                    )

        if not shot_attempts:
            return pd.DataFrame(
                {"nhl_api_player_id": [], "corsi_for": [], "fenwick_for": [], "missed_shots": []}
            )

        # Convert to DataFrame for easier aggregation
        df = pd.DataFrame(shot_attempts)

        # Calculate Corsi (all shot attempts)
        corsi = df.groupby("nhl_api_player_id").size().to_frame(name="corsi_for").reset_index()

        # Calculate Fenwick (shot attempts excluding blocked shots)
        fenwick = (
            df[df["play_type"] != "blocked-shot"]
            .groupby("nhl_api_player_id")
            .size()
            .to_frame(name="fenwick_for")
            .reset_index()
        )

        # Calculate missed shots
        missed = (
            df[df["play_type"] == "missed-shot"]
            .groupby("nhl_api_player_id")
            .size()
            .to_frame(name="missed_shots")
            .reset_index()
        )

        # Merge all stats together
        stats = corsi.merge(fenwick, on="nhl_api_player_id", how="left")
        stats = stats.merge(missed, on="nhl_api_player_id", how="left")

        # Fill NaN values with 0
        stats = stats.fillna(0).astype({"corsi_for": int, "fenwick_for": int, "missed_shots": int})

        logger.debug(f"Calculated Corsi/Fenwick for {len(stats)} players in game {game_id}")
        return stats

    except Exception as e:
        logger.error(f"Error calculating Corsi/Fenwick for game {game_id}: {e}")
        return pd.DataFrame(
            {"nhl_api_player_id": [], "corsi_for": [], "fenwick_for": [], "missed_shots": []}
        )


def fetch_boxscore_data(date_str: str) -> list[dict[str, int | str | float | None]]:
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

    if not schedule or "games" not in schedule:
        logger.warning(f"No games found for {date_str}")
        return []

    games = schedule["games"]

    if not games:
        logger.warning(f"No games found for {date_str}")
        return []

    logger.info(f"Found {len(games)} games on {date_str}")

    all_player_stats = []

    for game in games:
        game_id = game["id"]
        logger.info(f"Fetching boxscore and play-by-play for game {game_id}")

        try:
            # Fetch boxscore data
            boxscore = client.game_center.boxscore(game_id)

            if not boxscore or "playerByGameStats" not in boxscore:
                logger.warning(f"No boxscore data for game {game_id}")
                continue

            # Fetch Corsi/Fenwick data from play-by-play
            corsi_fenwick_df = calculate_corsi_fenwick_from_playbyplay(client, game_id)

            player_stats = boxscore["playerByGameStats"]
            game_player_stats = []

            # Process away team players
            if "awayTeam" in player_stats:
                for position in ["forwards", "defense"]:
                    if position in player_stats["awayTeam"]:
                        for player in player_stats["awayTeam"][position]:
                            player_dict = extract_player_stats(player, game_id, date_str)
                            if player_dict:
                                game_player_stats.append(player_dict)

            # Process home team players
            if "homeTeam" in player_stats:
                for position in ["forwards", "defense"]:
                    if position in player_stats["homeTeam"]:
                        for player in player_stats["homeTeam"][position]:
                            player_dict = extract_player_stats(player, game_id, date_str)
                            if player_dict:
                                game_player_stats.append(player_dict)

            # Merge Corsi/Fenwick data using pandas
            if game_player_stats:
                game_stats_df = pd.DataFrame(game_player_stats)

                if not corsi_fenwick_df.empty:
                    # Merge Corsi/Fenwick stats into player stats
                    game_stats_df = game_stats_df.merge(
                        corsi_fenwick_df, on="nhl_api_player_id", how="left", suffixes=("", "_pbp")
                    )

                    # Update the corsi/fenwick columns with play-by-play data
                    corsi_col = game_stats_df["corsi_for_pbp"].fillna(0).astype(int)
                    fenwick_col = game_stats_df["fenwick_for_pbp"].fillna(0).astype(int)
                    missed_col = game_stats_df["missed_shots_pbp"].fillna(0).astype(int)
                    game_stats_df["corsi_for"] = corsi_col
                    game_stats_df["fenwick_for"] = fenwick_col
                    game_stats_df["missed_shots"] = missed_col

                    # Drop the temporary merge columns
                    drop_cols = ["corsi_for_pbp", "fenwick_for_pbp", "missed_shots_pbp"]
                    game_stats_df = game_stats_df.drop(columns=drop_cols)

                # Add this game's stats to the overall list
                all_player_stats.extend(game_stats_df.to_dict("records"))

        except Exception as e:
            logger.error(f"Error fetching data for game {game_id}: {e}")
            continue

    logger.info(f"Fetched stats for {len(all_player_stats)} players")
    return all_player_stats


def extract_player_stats(
    player: dict[str, int | str | float], game_id: int, game_date: str
) -> dict[str, int | str | float | None] | None:
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
        # Extract player name from the 'name' field
        name_data = player.get("name", {})
        full_name = name_data.get("default", "") if isinstance(name_data, dict) else ""

        # Parse first and last name from full name
        # Format is typically "F. Lastname" or "Firstname Lastname"
        first_name = ""
        last_name = ""
        if full_name:
            name_parts = full_name.split(" ", 1)
            if len(name_parts) == 2:
                first_name = name_parts[0]
                last_name = name_parts[1]
            else:
                last_name = full_name

        return {
            "nhl_api_player_id": player.get("playerId"),
            "nhl_api_game_id": game_id,
            "game_date": game_date,
            "full_name": full_name,
            "first_name": first_name,
            "last_name": last_name,
            "goals": player.get("goals", 0),
            "assists": player.get("assists", 0),
            "points": player.get("points", 0),
            "plus_minus": player.get("plusMinus", 0),
            "pim": player.get("pim", 0),
            "hits": player.get("hits", 0),
            "power_play_goals": player.get("powerPlayGoals", 0),
            "sog": player.get("sog", 0),
            "faceoff_winning_pctg": player.get("faceoffWinningPctg", 0.0),
            "toi": player.get("toi", "00:00"),
            "blocked_shots": player.get("blockedShots", 0),
            "shifts": player.get("shifts", 0),
            "giveaways": player.get("giveaways", 0),
            "takeaways": player.get("takeaways", 0),
            "corsi_for": 0,  # Will be filled from play-by-play data
            "fenwick_for": 0,  # Will be filled from play-by-play data
            "missed_shots": 0,  # Will be filled from play-by-play data
        }
    except (KeyError, TypeError) as e:
        logger.warning(f"Error extracting stats for player: {e}")
        return None


def insert_player_stats(
    conn: duckdb.DuckDBPyConnection,
    player_stats: list[dict[str, int | str | float | None]],
) -> None:
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
        INSERT OR REPLACE INTO nhl_player_game_stats
        SELECT
            nhl_api_player_id,
            nhl_api_game_id,
            game_date,
            full_name,
            first_name,
            last_name,
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
            takeaways,
            corsi_for,
            fenwick_for,
            missed_shots
        FROM df
    """)

    logger.info(f"Successfully inserted {len(df)} player records")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Fetch NHL box scores for a date and insert into DuckDB"
    )
    _ = parser.add_argument("date", type=str, help="Date in YYYY-MM-DD format (e.g., 2025-12-06)")
    _ = parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Validate date format
    try:
        datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        logger.error(f"Invalid date format: {args.date}. Use YYYY-MM-DD")
        sys.exit(1)

    # Connect to database and ensure table exists
    conn = get_nhl_stats_db_connection()
    create_nhl_player_game_stats_table(conn)

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
