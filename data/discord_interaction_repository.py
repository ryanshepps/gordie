"""Repository for Discord interaction response targets."""

from dataclasses import dataclass
from typing import cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from data.repository import DatabaseRow, Repository


@dataclass(frozen=True, slots=True)
class DiscordInteractionTarget:
    """Latest Discord response target for a conversation thread."""

    thread_id: str
    application_id: str
    interaction_token: str


class DiscordInteractionRepository(Repository):
    """Store the latest Discord interaction token per core conversation thread."""

    def __init__(self, session: Session | None = None) -> None:
        super().__init__("discord_interaction_targets", session)

    def upsert_target(
        self,
        thread_id: str,
        application_id: str,
        interaction_token: str,
    ) -> None:
        """Save the latest Discord response target for a thread."""
        _ = self.session.execute(
            text(
                """
                INSERT INTO discord_interaction_targets
                    (thread_id, application_id, interaction_token)
                VALUES (:thread_id, :application_id, :interaction_token)
                ON CONFLICT (thread_id) DO UPDATE SET
                    application_id = EXCLUDED.application_id,
                    interaction_token = EXCLUDED.interaction_token,
                    updated_at = NOW()
                """
            ),
            {
                "thread_id": UUID(str(thread_id)),
                "application_id": application_id,
                "interaction_token": interaction_token,
            },
        )
        self.session.commit()

    def get_target(self, thread_id: str) -> DiscordInteractionTarget | None:
        """Return the latest Discord response target for a thread."""
        result: DatabaseRow | None = self.session.execute(
            text(
                """
                SELECT thread_id, application_id, interaction_token
                FROM discord_interaction_targets
                WHERE thread_id = :thread_id
                """
            ),
            {"thread_id": UUID(str(thread_id))},
        ).fetchone()
        if not result:
            return None
        thread_id_value = cast(object, result[0])
        application_id_value = cast(object, result[1])
        interaction_token_value = cast(object, result[2])
        return DiscordInteractionTarget(
            thread_id=str(thread_id_value),
            application_id=str(application_id_value),
            interaction_token=str(interaction_token_value),
        )
