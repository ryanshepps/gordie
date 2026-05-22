from __future__ import annotations

import json

from pydantic import BaseModel, Field

from agent.news.news_digest import RosterPlayer


class RosterPositionConfig(BaseModel):
    position: str
    count: int
    is_starting_position: bool


class LineupAnalysis(BaseModel):
    has_lineup_decisions: bool = False
    benched_players_with_games: list[str] = Field(default_factory=list)
    position_conflicts: dict[str, list[str]] = Field(default_factory=dict)


BENCH_SLOTS = {"BN", "IR", "IR+", "IL", "IL+", "NA"}
IR_SLOTS = {"IR", "IR+", "IL", "IL+", "NA"}


def analyze_lineup(
    roster_players: list[RosterPlayer],
    teams_playing_today: set[str],
    roster_position_configs: list[RosterPositionConfig],
) -> LineupAnalysis:
    active_slot_counts: dict[str, int] = {}
    for config in roster_position_configs:
        if config.is_starting_position and config.position not in BENCH_SLOTS:
            active_slot_counts[config.position] = config.count

    playing_and_available = [
        p for p in roster_players if p.team in teams_playing_today and p.roster_slot not in IR_SLOTS
    ]

    position_conflicts: dict[str, list[str]] = {}
    for slot_position, max_count in active_slot_counts.items():
        if slot_position == "Util":
            continue

        eligible = [p for p in playing_and_available if p.position == slot_position]
        if len(eligible) > max_count:
            util_slots = active_slot_counts.get("Util", 0)
            overflow = len(eligible) - max_count
            if overflow > util_slots:
                position_conflicts[slot_position] = [p.name for p in eligible]

    benched_with_games: list[str] = []
    for player in roster_players:
        if player.team not in teams_playing_today:
            continue
        if player.roster_slot not in BENCH_SLOTS:
            continue
        if player.roster_slot in IR_SLOTS:
            continue

        primary_slot = player.position
        active_in_primary = sum(1 for p in roster_players if p.roster_slot == primary_slot)
        max_primary = active_slot_counts.get(primary_slot, 0)
        if active_in_primary < max_primary:
            benched_with_games.append(player.name)
            continue

        active_in_util = sum(1 for p in roster_players if p.roster_slot == "Util")
        max_util = active_slot_counts.get("Util", 0)
        if active_in_util < max_util:
            benched_with_games.append(player.name)

    has_decisions = bool(position_conflicts) or bool(benched_with_games)

    return LineupAnalysis(
        has_lineup_decisions=has_decisions,
        benched_players_with_games=benched_with_games,
        position_conflicts=position_conflicts,
    )


def parse_roster_position_configs(league_settings_json: str) -> list[RosterPositionConfig]:
    try:
        settings = json.loads(league_settings_json)
    except (json.JSONDecodeError, TypeError):
        return []

    roster_positions_raw = settings.get("roster_positions", [])

    if isinstance(roster_positions_raw, dict):
        roster_positions_raw = roster_positions_raw.get("roster_position", [])

    if not isinstance(roster_positions_raw, list):
        return []

    configs: list[RosterPositionConfig] = []
    for rp in roster_positions_raw:
        if isinstance(rp, dict):
            pos_data = rp.get("roster_position", rp)
            position = pos_data.get("position", "")
            count = int(pos_data.get("count", 0))
            is_starting = pos_data.get("is_starting_position", False)
            if isinstance(is_starting, str):
                is_starting = is_starting.lower() == "true" or is_starting == "1"
            configs.append(
                RosterPositionConfig(
                    position=position,
                    count=count,
                    is_starting_position=bool(is_starting),
                )
            )

    return configs
