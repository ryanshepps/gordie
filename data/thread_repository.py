"""Repository for canonical per-user conversation threads."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from data.models import Medium
from data.repository import DatabaseRow, Repository


@dataclass(frozen=True, slots=True)
class ThreadRecord:
    id: UUID
    user_id: UUID
    medium: Medium
    is_new_thread: bool

    @property
    def thread_id(self) -> str:
        return str(self.id)


class ThreadRepository(Repository):
    """Repository for resolving one LangGraph thread per user and medium."""

    def __init__(self, session: Session | None = None) -> None:
        super().__init__("conversation_threads", session)

    def resolve(self, user_id: UUID, medium: Medium) -> ThreadRecord:
        """Return the existing thread for a user+medium or create it."""
        existing = self.get_by(user_id=user_id, medium=medium.value)
        if existing:
            thread_id = UUID(str(existing[0]))
            self.session.execute(
                text("UPDATE conversation_threads SET last_active = NOW() WHERE id = :id"),
                {"id": thread_id},
            )
            self.session.commit()
            return ThreadRecord(
                id=thread_id,
                user_id=UUID(str(existing[1])),
                medium=Medium(str(existing[2])),
                is_new_thread=False,
            )

        thread_id = uuid4()
        try:
            self.insert(id=thread_id, user_id=user_id, medium=medium.value)
        except IntegrityError:
            self.session.rollback()
            existing = self.get_by(user_id=user_id, medium=medium.value)
            if existing:
                thread_id = UUID(str(existing[0]))
                self.session.execute(
                    text("UPDATE conversation_threads SET last_active = NOW() WHERE id = :id"),
                    {"id": thread_id},
                )
                self.session.commit()
                return ThreadRecord(
                    id=thread_id,
                    user_id=UUID(str(existing[1])),
                    medium=Medium(str(existing[2])),
                    is_new_thread=False,
                )
            raise RuntimeError(
                "Thread creation conflicted but no existing thread was found"
            ) from None
        return ThreadRecord(id=thread_id, user_id=user_id, medium=medium, is_new_thread=True)

    def get_sms_external_id(self, thread_id: str) -> str | None:
        """Return the SMS external ID for a conversation thread, if it has one."""
        result: DatabaseRow | None = self.session.execute(
            text(
                """
                SELECT ui.external_id
                FROM conversation_threads ct
                JOIN user_identities ui
                    ON ui.user_id = ct.user_id AND ui.medium = :medium
                WHERE ct.id = :thread_id
                """
            ),
            {"thread_id": thread_id, "medium": Medium.SMS.value},
        ).fetchone()
        if not result:
            return None
        return str(result[0])
