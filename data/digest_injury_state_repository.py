from __future__ import annotations

from sqlalchemy.orm import Session

from data.repository import Repository


class DigestInjuryStateRepository(Repository):

    def __init__(self, session: Session | None = None):
        super().__init__("digest_injury_states", session)

    def get_previous_states(self, user_email: str) -> dict[str, str]:
        rows = self.get_all(user_email=user_email)
        return {row[1]: row[2] for row in rows}

    def save_current_states(self, user_email: str, states: dict[str, str]) -> None:
        self.delete(user_email=user_email)
        for player_name, status in states.items():
            self.insert(
                user_email=user_email,
                player_name=player_name,
                status=status,
            )
