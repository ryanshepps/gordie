from __future__ import annotations

from sqlalchemy.orm import Session

from data.models import Medium
from data.repository import Repository
from data.user_repository import UserRepository


class DigestInjuryStateRepository(Repository):
    def __init__(self, session: Session | None = None) -> None:
        super().__init__("digest_injury_states", session)

    def get_previous_states(self, user_email: str) -> dict[str, str]:
        user_id = UserRepository(self.session).resolve_user_id(Medium.EMAIL, user_email, user_email)
        rows = self.get_all(user_id=user_id)
        return {row[1]: row[2] for row in rows}

    def save_current_states(self, user_email: str, states: dict[str, str]) -> None:
        user_id = UserRepository(self.session).resolve_user_id(Medium.EMAIL, user_email, user_email)
        self.delete(user_id=user_id)
        for player_name, status in states.items():
            self.insert(
                user_id=user_id,
                player_name=player_name,
                status=status,
            )
