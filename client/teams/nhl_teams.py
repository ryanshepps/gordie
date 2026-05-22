from __future__ import annotations

NHL_TEAMS: dict[str, str] = {
    "ANA": "Anaheim Ducks",
    "ARI": "Arizona Coyotes",
    "BOS": "Boston Bruins",
    "BUF": "Buffalo Sabres",
    "CGY": "Calgary Flames",
    "CAR": "Carolina Hurricanes",
    "CHI": "Chicago Blackhawks",
    "COL": "Colorado Avalanche",
    "CBJ": "Columbus Blue Jackets",
    "DAL": "Dallas Stars",
    "DET": "Detroit Red Wings",
    "EDM": "Edmonton Oilers",
    "FLA": "Florida Panthers",
    "LAK": "Los Angeles Kings",
    "MIN": "Minnesota Wild",
    "MTL": "Montreal Canadiens",
    "NSH": "Nashville Predators",
    "NJD": "New Jersey Devils",
    "NYI": "New York Islanders",
    "NYR": "New York Rangers",
    "OTT": "Ottawa Senators",
    "PHI": "Philadelphia Flyers",
    "PIT": "Pittsburgh Penguins",
    "SJS": "San Jose Sharks",
    "SEA": "Seattle Kraken",
    "STL": "St. Louis Blues",
    "TBL": "Tampa Bay Lightning",
    "TOR": "Toronto Maple Leafs",
    "UTA": "Utah Hockey Club",
    "VAN": "Vancouver Canucks",
    "VGK": "Vegas Golden Knights",
    "WSH": "Washington Capitals",
    "WPG": "Winnipeg Jets",
}

NHL_TEAMS_BY_NAME: dict[str, str] = {name: abbr for abbr, name in NHL_TEAMS.items()}

NHL_TEAMS_BY_NAME_LOWER: dict[str, str] = {
    name.lower(): abbr for name, abbr in NHL_TEAMS_BY_NAME.items()
}


def nhl_team_abbr(team_name: str) -> str:
    if team_name in NHL_TEAMS_BY_NAME:
        return NHL_TEAMS_BY_NAME[team_name]

    normalized = team_name.lower().strip()

    if normalized in NHL_TEAMS_BY_NAME_LOWER:
        return NHL_TEAMS_BY_NAME_LOWER[normalized]

    if team_name.upper() in NHL_TEAMS:
        return team_name.upper()

    for full_name_lower, abbr in NHL_TEAMS_BY_NAME_LOWER.items():
        if normalized in full_name_lower or full_name_lower in normalized:
            return abbr

    return team_name.upper()[:3]
