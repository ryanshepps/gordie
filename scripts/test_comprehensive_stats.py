"""Test script for the comprehensive player stats tool."""

import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.player_comparison.get_comprehensive_player_stats import (
    get_comprehensive_player_stats,
)


def test_comprehensive_stats():
    """Test the comprehensive player stats tool with a few players."""
    # You'll need to set these environment variables or pass them as arguments
    user_email = os.getenv("USER_EMAIL", "your-email@example.com")
    league_id = os.getenv("LEAGUE_ID", "your-league-id")

    # Test with a few well-known players
    player_names = ["Connor McDavid", "Nathan MacKinnon", "Auston Matthews"]

    print(f"Testing comprehensive stats for: {', '.join(player_names)}\n")

    result = get_comprehensive_player_stats.invoke({
        "player_names": player_names,
        "user_email": user_email,
        "league_id": league_id,
        "situation": "all",
        "season": 2024,
    })

    # Pretty print the results
    data = json.loads(result)
    print(json.dumps(data, indent=2))

    # Verify structure
    print("\n--- Verification ---")
    for player_name in player_names:
        if player_name in data:
            player_data = data[player_name]
            status = player_data.get("status")
            print(f"\n{player_name}: {status}")

            if status == "success":
                print(f"  - NHL ID: {player_data.get('nhl_api_id')}")
                print(f"  - Team: {player_data.get('team')}")
                print(f"  - Yahoo Rank: {player_data.get('yahoo_rank')}")
                print(f"  - Goals: {player_data.get('goals')}")
                print(f"  - Points: {player_data.get('points')}")
                print(f"  - xGoals: {player_data.get('x_goals')}")
                print(f"  - Fenwick%: {player_data.get('fenwick_pct')}")
                print(f"  - Games this week: {player_data.get('games_remaining_this_week')}")
                print(f"  - Games next week: {player_data.get('games_next_week')}")
                print(f"  - Line: {player_data.get('estimated_line_number')}")

                linemates = player_data.get("primary_linemates", [])
                if linemates:
                    print("  - Primary linemates:")
                    for lm in linemates:
                        print(
                            f"    - {lm.get('name')} (ID: {lm.get('player_id')}) - {lm.get('shared_ice_time_pct')}% shared ice time"
                        )

                if player_data.get("warnings"):
                    print(f"  - Warnings: {player_data['warnings']}")
            else:
                print(f"  - Error: {player_data.get('error')}")


if __name__ == "__main__":
    test_comprehensive_stats()
