"""Central config — environment-driven values used across the app.

Read once at import; values are read from `os.environ` and frozen at module load
to keep behaviour deterministic. Override in tests via `monkeypatch.setenv` plus
`importlib.reload(module.config)` if you must.
"""

import os

# LLM provider/model. Provider is informational; the factory in module.llm
# picks the actual client based on this.
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai").lower()
LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")

# Sports the agent should service. Comma-separated env, lowercased set.
_RAW_SPORTS = os.getenv("ENABLED_SPORTS", "nhl,mlb")
ENABLED_SPORTS: frozenset[str] = frozenset(
    s.strip().lower() for s in _RAW_SPORTS.split(",") if s.strip()
)


def sport_enabled(sport: str) -> bool:
    """Return True when the named sport is enabled via ENABLED_SPORTS."""
    return sport.lower() in ENABLED_SPORTS
