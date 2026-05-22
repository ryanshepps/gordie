from __future__ import annotations

MLB_TEAMS: dict[str, str] = {
    "ARI": "Arizona Diamondbacks",
    "ATL": "Atlanta Braves",
    "BAL": "Baltimore Orioles",
    "BOS": "Boston Red Sox",
    "CHC": "Chicago Cubs",
    "CWS": "Chicago White Sox",
    "CIN": "Cincinnati Reds",
    "CLE": "Cleveland Guardians",
    "COL": "Colorado Rockies",
    "DET": "Detroit Tigers",
    "HOU": "Houston Astros",
    "KC": "Kansas City Royals",
    "LAA": "Los Angeles Angels",
    "LAD": "Los Angeles Dodgers",
    "MIA": "Miami Marlins",
    "MIL": "Milwaukee Brewers",
    "MIN": "Minnesota Twins",
    "NYM": "New York Mets",
    "NYY": "New York Yankees",
    "OAK": "Oakland Athletics",
    "PHI": "Philadelphia Phillies",
    "PIT": "Pittsburgh Pirates",
    "SD": "San Diego Padres",
    "SF": "San Francisco Giants",
    "SEA": "Seattle Mariners",
    "STL": "St. Louis Cardinals",
    "TB": "Tampa Bay Rays",
    "TEX": "Texas Rangers",
    "TOR": "Toronto Blue Jays",
    "WSH": "Washington Nationals",
}

MLB_TEAMS_BY_NAME: dict[str, str] = {name: abbr for abbr, name in MLB_TEAMS.items()}

MLB_TEAMS_BY_NAME_LOWER: dict[str, str] = {
    name.lower(): abbr for name, abbr in MLB_TEAMS_BY_NAME.items()
}


def mlb_team_abbr(team_name: str) -> str:
    if team_name in MLB_TEAMS_BY_NAME:
        return MLB_TEAMS_BY_NAME[team_name]

    normalized = team_name.lower().strip()

    if normalized in MLB_TEAMS_BY_NAME_LOWER:
        return MLB_TEAMS_BY_NAME_LOWER[normalized]

    if team_name.upper() in MLB_TEAMS:
        return team_name.upper()

    for full_name_lower, abbr in MLB_TEAMS_BY_NAME_LOWER.items():
        if normalized in full_name_lower or full_name_lower in normalized:
            return abbr

    return team_name.upper()[:3]
