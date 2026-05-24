"""Repository helpers for hosted temporary trial sessions."""

import secrets
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from data.models import Medium
from data.repository import Repository
from data.user_repository import UserRepository

TRIAL_PROVIDER = "yahoo"


class TrialSessionError(RuntimeError):
    """Base error for temporary trial sessions."""


class TrialSessionExpiredError(TrialSessionError):
    """Raised when a temporary session is missing or expired."""


class TrialProviderRequiredError(TrialSessionError):
    """Raised when a question requires a linked fantasy provider."""


class TrialLimitExceededError(TrialSessionError):
    """Raised when the session or provider account has used its trial quota."""


@dataclass(frozen=True, slots=True)
class TemporarySessionRecord:
    id: UUID
    user_id: UUID
    question_count: int
    question_limit: int
    expires_at: datetime

    @property
    def remaining_questions(self) -> int:
        return max(self.question_limit - self.question_count, 0)


@dataclass(frozen=True, slots=True)
class ProviderConnectionRecord:
    id: UUID
    provider: str
    provider_user_id: str
    provider_email: str | None
    temporary_session_id: UUID | None
    user_id: UUID | None
    question_count: int
    question_limit: int

    @property
    def remaining_questions(self) -> int:
        return max(self.question_limit - self.question_count, 0)


@dataclass(frozen=True, slots=True)
class CreatedTemporarySession:
    session: TemporarySessionRecord
    token: str


@dataclass(frozen=True, slots=True)
class TrialQuestionReservation:
    session: TemporarySessionRecord
    provider_connection: ProviderConnectionRecord

    @property
    def remaining_questions(self) -> int:
        return min(
            self.session.remaining_questions,
            self.provider_connection.remaining_questions,
        )


@dataclass(frozen=True, slots=True)
class TemporarySaveLink:
    email: str
    token: str


class TemporarySessionRepository(Repository):
    """Repository for temporary hosted-trial sessions and trial caps."""

    def __init__(self, session: Session | None = None) -> None:
        super().__init__("temporary_sessions", session)

    def create_session(
        self,
        ttl_days: int = 7,
        question_limit: int = 5,
    ) -> CreatedTemporarySession:
        """Create a temporary session backed by an anonymous web user."""
        session_id = uuid4()
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(days=ttl_days)

        user_repo = UserRepository(self.session)
        user_id = user_repo.create_with_identity(
            Medium.WEB,
            self._web_external_id(session_id),
            "Temporary Web Session",
        )

        _ = self.session.execute(
            text(
                """
                INSERT INTO temporary_sessions (
                    id, session_token_hash, user_id, question_limit, expires_at
                )
                VALUES (
                    :id, :session_token_hash, :user_id, :question_limit, :expires_at
                )
                """
            ),
            {
                "id": session_id,
                "session_token_hash": self.hash_token(token),
                "user_id": user_id,
                "question_limit": question_limit,
                "expires_at": expires_at,
            },
        )
        self.session.commit()
        session = self.get_by_id(session_id)
        if session is None:
            raise TrialSessionError("Temporary session was not created")
        return CreatedTemporarySession(session=session, token=token)

    def get_by_token(self, token: str) -> TemporarySessionRecord | None:
        """Return the active session for a raw browser token."""
        row: Sequence[object] | None = self.session.execute(
            text(
                """
                SELECT id, user_id, question_count, question_limit, expires_at
                FROM temporary_sessions
                WHERE session_token_hash = :session_token_hash
                    AND expires_at > NOW()
                """
            ),
            {"session_token_hash": self.hash_token(token)},
        ).fetchone()
        return self._session_from_row(row)

    def get_by_id(self, session_id: UUID) -> TemporarySessionRecord | None:
        """Return a temporary session by ID."""
        row = self.session.execute(
            text(
                """
                SELECT id, user_id, question_count, question_limit, expires_at
                FROM temporary_sessions
                WHERE id = :session_id
                    AND expires_at > NOW()
                """
            ),
            {"session_id": session_id},
        ).fetchone()
        return self._session_from_row(row)

    def upsert_provider_connection(
        self,
        session_id: UUID,
        user_id: UUID,
        provider_user_id: str,
        provider_email: str | None,
        question_limit: int = 5,
    ) -> ProviderConnectionRecord:
        """Link a Yahoo provider identity to a temporary session."""
        _ = self.session.execute(
            text(
                """
                INSERT INTO fantasy_provider_connections (
                    provider,
                    provider_user_id,
                    provider_email,
                    temporary_session_id,
                    user_id,
                    question_limit,
                    connected_at,
                    updated_at
                )
                VALUES (
                    :provider,
                    :provider_user_id,
                    :provider_email,
                    :temporary_session_id,
                    :user_id,
                    :question_limit,
                    NOW(),
                    NOW()
                )
                ON CONFLICT (provider, provider_user_id) DO UPDATE SET
                    provider_email = EXCLUDED.provider_email,
                    temporary_session_id = EXCLUDED.temporary_session_id,
                    user_id = EXCLUDED.user_id,
                    updated_at = NOW()
                """
            ),
            {
                "provider": TRIAL_PROVIDER,
                "provider_user_id": provider_user_id,
                "provider_email": provider_email,
                "temporary_session_id": session_id,
                "user_id": user_id,
                "question_limit": question_limit,
            },
        )
        self.session.commit()

        connection = self.get_provider_connection(session_id)
        if connection is None:
            raise TrialSessionError("Provider connection was not created")
        return connection

    def get_provider_connection(self, session_id: UUID) -> ProviderConnectionRecord | None:
        """Return the Yahoo connection for a temporary session."""
        row = self.session.execute(
            text(
                """
                SELECT
                    id,
                    provider,
                    provider_user_id,
                    provider_email,
                    temporary_session_id,
                    user_id,
                    question_count,
                    question_limit
                FROM fantasy_provider_connections
                WHERE provider = :provider
                    AND temporary_session_id = :temporary_session_id
                """
            ),
            {"provider": TRIAL_PROVIDER, "temporary_session_id": session_id},
        ).fetchone()
        return self._connection_from_row(row)

    def reserve_question(self, session_id: UUID) -> TrialQuestionReservation:
        """Atomically reserve one trial question on both session and provider caps."""
        try:
            session_row = self.session.execute(
                text(
                    """
                    SELECT id, user_id, question_count, question_limit, expires_at
                    FROM temporary_sessions
                    WHERE id = :session_id
                        AND expires_at > NOW()
                    FOR UPDATE
                    """
                ),
                {"session_id": session_id},
            ).fetchone()
            session = self._session_from_row(session_row)
            if session is None:
                raise TrialSessionExpiredError("Temporary session is expired or missing")
            if session.question_count >= session.question_limit:
                raise TrialLimitExceededError("This temporary session has used its trial questions")

            connection_row = self.session.execute(
                text(
                    """
                    SELECT
                        id,
                        provider,
                        provider_user_id,
                        provider_email,
                        temporary_session_id,
                        user_id,
                        question_count,
                        question_limit
                    FROM fantasy_provider_connections
                    WHERE provider = :provider
                        AND temporary_session_id = :temporary_session_id
                    FOR UPDATE
                    """
                ),
                {"provider": TRIAL_PROVIDER, "temporary_session_id": session_id},
            ).fetchone()
            connection = self._connection_from_row(connection_row)
            if connection is None:
                raise TrialProviderRequiredError("Connect Yahoo Fantasy before asking a question")
            if connection.question_count >= connection.question_limit:
                raise TrialLimitExceededError(
                    "This Yahoo account has used its hosted-trial questions"
                )

            _ = self.session.execute(
                text(
                    """
                    UPDATE temporary_sessions
                    SET question_count = question_count + 1,
                        updated_at = NOW()
                    WHERE id = :session_id
                    """
                ),
                {"session_id": session_id},
            )
            _ = self.session.execute(
                text(
                    """
                    UPDATE fantasy_provider_connections
                    SET question_count = question_count + 1,
                        updated_at = NOW()
                    WHERE id = :connection_id
                    """
                ),
                {"connection_id": connection.id},
            )
            self.session.commit()
        except TrialSessionError:
            self.session.rollback()
            raise

        updated_session = self.get_by_id(session_id)
        updated_connection = self.get_provider_connection(session_id)
        if updated_session is None or updated_connection is None:
            raise TrialSessionError("Trial reservation could not be reloaded")
        return TrialQuestionReservation(
            session=updated_session,
            provider_connection=updated_connection,
        )

    def add_chat_message(self, session_id: UUID, role: str, content: str) -> None:
        """Persist a temporary chat message with the session expiry as retention."""
        session = self.get_by_id(session_id)
        if session is None:
            raise TrialSessionExpiredError("Temporary session is expired or missing")
        _ = self.session.execute(
            text(
                """
                INSERT INTO temporary_chat_messages (
                    temporary_session_id, role, content, expires_at
                )
                VALUES (:session_id, :role, :content, :expires_at)
                """
            ),
            {
                "session_id": session_id,
                "role": role,
                "content": content,
                "expires_at": session.expires_at,
            },
        )
        self.session.commit()

    def create_save_link(
        self,
        session_id: UUID,
        email: str,
        ttl_minutes: int = 30,
    ) -> TemporarySaveLink:
        """Create a short-lived email magic link for a temporary session."""
        session = self.get_by_id(session_id)
        if session is None:
            raise TrialSessionExpiredError("Temporary session is expired or missing")

        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(minutes=ttl_minutes)
        _ = self.session.execute(
            text(
                """
                INSERT INTO temporary_session_save_links (
                    temporary_session_id, email, token_hash, expires_at
                )
                VALUES (:session_id, :email, :token_hash, :expires_at)
                """
            ),
            {
                "session_id": session_id,
                "email": email,
                "token_hash": self.hash_token(token),
                "expires_at": expires_at,
            },
        )
        self.session.commit()
        return TemporarySaveLink(email=email, token=token)

    def confirm_save_link(self, token: str) -> CreatedTemporarySession:
        """Mark a save link used, attach email identity, and rotate the session token."""
        row = cast(
            Sequence[object] | None,
            self.session.execute(
                text(
                    """
                    SELECT temporary_session_id, email
                    FROM temporary_session_save_links
                    WHERE token_hash = :token_hash
                        AND used_at IS NULL
                        AND expires_at > NOW()
                    FOR UPDATE
                    """
                ),
                {"token_hash": self.hash_token(token)},
            ).fetchone(),
        )
        if row is None:
            raise TrialSessionExpiredError("This save link is expired or has already been used")

        save_link_values = tuple(row)
        session_id = UUID(str(save_link_values[0]))
        email = str(save_link_values[1]).strip().lower()
        session = self.get_by_id(session_id)
        if session is None:
            raise TrialSessionExpiredError("Temporary session is expired or missing")

        user_repo = UserRepository(self.session)
        existing_email_user = cast(
            Sequence[object] | None,
            user_repo.get_by_identity(Medium.EMAIL, email),
        )
        if existing_email_user and UUID(str(existing_email_user[0])) != session.user_id:
            raise TrialSessionError("That email is already linked to another Gordie user")
        if not existing_email_user:
            _ = self.session.execute(
                text(
                    """
                    INSERT INTO user_identities (user_id, medium, external_id, display_name)
                    VALUES (:user_id, :medium, :external_id, :display_name)
                    """
                ),
                {
                    "user_id": session.user_id,
                    "medium": Medium.EMAIL.value,
                    "external_id": email,
                    "display_name": email,
                },
            )

        new_token = secrets.token_urlsafe(32)
        _ = self.session.execute(
            text(
                """
                UPDATE temporary_sessions
                SET session_token_hash = :session_token_hash,
                    converted_user_id = :user_id,
                    updated_at = NOW()
                WHERE id = :session_id
                """
            ),
            {
                "session_id": session_id,
                "session_token_hash": self.hash_token(new_token),
                "user_id": session.user_id,
            },
        )
        _ = self.session.execute(
            text(
                """
                UPDATE temporary_session_save_links
                SET used_at = NOW()
                WHERE token_hash = :token_hash
                """
            ),
            {"token_hash": self.hash_token(token)},
        )
        self.session.commit()

        updated_session = self.get_by_id(session_id)
        if updated_session is None:
            raise TrialSessionError("Temporary session could not be reloaded")
        return CreatedTemporarySession(session=updated_session, token=new_token)

    def cleanup_expired(self) -> int:
        """Delete expired temporary sessions and provider tokens for anonymous users."""
        converted_rows = cast(
            Sequence[Sequence[object]],
            self.session.execute(
                text(
                    """
                    SELECT id
                    FROM temporary_sessions
                    WHERE expires_at < NOW()
                        AND converted_user_id IS NOT NULL
                    """
                )
            ).fetchall(),
        )
        converted_session_ids = [UUID(str(row[0])) for row in converted_rows]
        expired_rows = cast(
            Sequence[Sequence[object]],
            self.session.execute(
                text(
                    """
                    SELECT id, user_id
                    FROM temporary_sessions
                    WHERE expires_at < NOW()
                        AND converted_user_id IS NULL
                    """
                )
            ).fetchall(),
        )
        expired_pairs = [(UUID(str(row[0])), UUID(str(row[1]))) for row in expired_rows]

        _ = self.session.execute(
            text("DELETE FROM temporary_chat_messages WHERE expires_at < NOW()")
        )
        _ = self.session.execute(
            text("DELETE FROM temporary_session_save_links WHERE expires_at < NOW()")
        )

        for session_id in converted_session_ids:
            params = {"session_id": session_id}
            _ = self.session.execute(
                text(
                    """
                    UPDATE fantasy_provider_connections
                    SET temporary_session_id = NULL,
                        updated_at = NOW()
                    WHERE temporary_session_id = :session_id
                    """
                ),
                params,
            )
            _ = self.session.execute(
                text("DELETE FROM temporary_sessions WHERE id = :session_id"),
                params,
            )

        for session_id, user_id in expired_pairs:
            params = {"session_id": session_id, "user_id": user_id}
            _ = self.session.execute(
                text(
                    """
                    DELETE FROM fantasy_provider_connections
                    WHERE temporary_session_id = :session_id
                    """
                ),
                params,
            )
            _ = self.session.execute(
                text("DELETE FROM yahoo_user_teams WHERE user_id = :user_id"),
                params,
            )
            _ = self.session.execute(
                text("DELETE FROM yahoo_tokens WHERE user_id = :user_id"),
                params,
            )
            _ = self.session.execute(
                text("DELETE FROM conversation_summaries WHERE user_id = :user_id"),
                params,
            )
            _ = self.session.execute(
                text("DELETE FROM conversation_threads WHERE user_id = :user_id"),
                params,
            )
            _ = self.session.execute(
                text("DELETE FROM user_identities WHERE user_id = :user_id"),
                params,
            )
            _ = self.session.execute(
                text("DELETE FROM temporary_sessions WHERE id = :session_id"),
                params,
            )
            _ = self.session.execute(
                text(
                    """
                    DELETE FROM users
                    WHERE id = :user_id
                        AND NOT EXISTS (
                            SELECT 1 FROM user_identities WHERE user_id = :user_id
                        )
                    """
                ),
                params,
            )

        self.session.commit()
        return len(expired_pairs)

    @staticmethod
    def hash_token(token: str) -> str:
        """Hash a raw session token for at-rest storage."""
        return sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _web_external_id(session_id: UUID) -> str:
        return f"trial:{session_id}"

    @staticmethod
    def _session_from_row(row: Sequence[object] | None) -> TemporarySessionRecord | None:
        if row is None:
            return None
        values = tuple(row)
        expires_at = values[4]
        if not isinstance(expires_at, datetime):
            expires_at = datetime.fromisoformat(str(expires_at))
        return TemporarySessionRecord(
            id=UUID(str(values[0])),
            user_id=UUID(str(values[1])),
            question_count=int(str(values[2])),
            question_limit=int(str(values[3])),
            expires_at=expires_at,
        )

    @staticmethod
    def _connection_from_row(row: Sequence[object] | None) -> ProviderConnectionRecord | None:
        if row is None:
            return None
        values = tuple(row)
        temporary_session_id = UUID(str(values[4])) if values[4] else None
        user_id = UUID(str(values[5])) if values[5] else None
        return ProviderConnectionRecord(
            id=UUID(str(values[0])),
            provider=str(values[1]),
            provider_user_id=str(values[2]),
            provider_email=str(values[3]) if values[3] else None,
            temporary_session_id=temporary_session_id,
            user_id=user_id,
            question_count=int(str(values[6])),
            question_limit=int(str(values[7])),
        )
