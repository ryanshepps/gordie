"""Repository for conversation messages and checkpoints."""

import json
from typing import Any

from psycopg.types.json import Json
from sqlalchemy import text

from data.database import get_session
from module.logger import get_logger

logger = get_logger(__name__)


class ConversationRepository:
    """Repository for accessing conversation messages and checkpoints."""

    def __init__(self):
        self.session = get_session()
        self._pending_commits = 0

    def commit(self) -> None:
        """Commit pending transactions if any."""
        if self._pending_commits > 0:
            self.session.commit()
            self._pending_commits = 0

    def rollback(self) -> None:
        """Rollback pending transactions."""
        if self._pending_commits > 0:
            self.session.rollback()
            self._pending_commits = 0

    def close(self):
        """Close the database session."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def add_message(
        self,
        thread_id: str,
        checkpoint_id: str,
        role: str,
        content: str,
        message_type: str = "standard",
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """
        Add a message to the conversation.

        Args:
            thread_id: The conversation thread ID
            checkpoint_id: The checkpoint ID this message belongs to
            role: Message role ('human', 'ai', or 'system')
            content: Message content
            message_type: Type of message ('standard', 'auto_ack', 'status')
            metadata: Optional metadata dict

        Returns:
            The ID of the inserted message
        """
        result = self.session.execute(
            text(
                """
                INSERT INTO conversation_messages
                (thread_id, checkpoint_id, role, content, message_type, metadata)
                VALUES (:thread_id, :checkpoint_id, :role, :content, :message_type, :metadata)
                RETURNING id
                """
            ),
            {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id,
                "role": role,
                "content": content,
                "message_type": message_type,
                "metadata": Json(metadata) if metadata else Json({}),
            },
        )
        self._pending_commits += 1
        message_id = result.scalar_one()
        logger.debug(f"Added message {message_id} to thread {thread_id}")
        return message_id

    def get_messages(
        self,
        thread_id: str,
        limit: int | None = None,
        message_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get messages for a thread.

        Args:
            thread_id: The conversation thread ID
            limit: Maximum number of messages to return (None for all)
            message_type: Filter by message type (None for all)

        Returns:
            List of message dicts with role, content, message_type, created_at
        """
        query = """
            SELECT role, content, message_type, created_at, metadata
            FROM conversation_messages
            WHERE thread_id = :thread_id
        """
        params: dict[str, Any] = {"thread_id": thread_id}

        if message_type:
            query += " AND message_type = :message_type"
            params["message_type"] = message_type

        query += " ORDER BY created_at ASC"

        if limit:
            query += " LIMIT :limit"
            params["limit"] = limit

        result = self.session.execute(text(query), params)
        rows = result.fetchall()

        return [
            {
                "role": row[0],
                "content": row[1],
                "message_type": row[2],
                "created_at": row[3].isoformat() if row[3] else None,
                "metadata": row[4] or {},
            }
            for row in rows
        ]

    def get_latest_checkpoint(
        self,
        thread_id: str,
        checkpoint_ns: str = "",
    ) -> dict[str, Any] | None:
        """
        Get the latest checkpoint for a thread.

        Args:
            thread_id: The conversation thread ID
            checkpoint_ns: Checkpoint namespace (usually empty string)

        Returns:
            Checkpoint dict or None if not found
        """
        result = self.session.execute(
            text(
                """
                SELECT thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id,
                       channel_values, metadata, created_at
                FROM conversation_checkpoints
                WHERE thread_id = :thread_id AND checkpoint_ns = :checkpoint_ns
                ORDER BY created_at DESC
                LIMIT 1
                """
            ),
            {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns},
        )
        row = result.fetchone()

        if not row:
            return None

        return {
            "thread_id": row[0],
            "checkpoint_ns": row[1],
            "checkpoint_id": row[2],
            "parent_checkpoint_id": row[3],
            "channel_values": row[4],
            "metadata": row[5],
            "created_at": row[6].isoformat() if row[6] else None,
        }

    def get_checkpoint(
        self,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
    ) -> dict[str, Any] | None:
        """
        Get a specific checkpoint by ID.

        Args:
            thread_id: The conversation thread ID
            checkpoint_ns: Checkpoint namespace
            checkpoint_id: The checkpoint ID

        Returns:
            Checkpoint dict or None if not found
        """
        result = self.session.execute(
            text(
                """
                SELECT thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id,
                       channel_values, metadata, created_at
                FROM conversation_checkpoints
                WHERE thread_id = :thread_id
                  AND checkpoint_ns = :checkpoint_ns
                  AND checkpoint_id = :checkpoint_id
                """
            ),
            {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            },
        )
        row = result.fetchone()

        if not row:
            return None

        return {
            "thread_id": row[0],
            "checkpoint_ns": row[1],
            "checkpoint_id": row[2],
            "parent_checkpoint_id": row[3],
            "channel_values": row[4],
            "metadata": row[5],
            "created_at": row[6].isoformat() if row[6] else None,
        }

    def list_checkpoints(
        self,
        thread_id: str,
        checkpoint_ns: str = "",
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        List checkpoints for a thread.

        Args:
            thread_id: The conversation thread ID
            checkpoint_ns: Checkpoint namespace
            limit: Maximum number of checkpoints to return

        Returns:
            List of checkpoint dicts
        """
        query = """
            SELECT thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id,
                   channel_values, metadata, created_at
            FROM conversation_checkpoints
            WHERE thread_id = :thread_id AND checkpoint_ns = :checkpoint_ns
            ORDER BY created_at DESC
        """
        params: dict[str, Any] = {
            "thread_id": thread_id,
            "checkpoint_ns": checkpoint_ns,
        }

        if limit:
            query += " LIMIT :limit"
            params["limit"] = limit

        result = self.session.execute(text(query), params)
        rows = result.fetchall()

        return [
            {
                "thread_id": row[0],
                "checkpoint_ns": row[1],
                "checkpoint_id": row[2],
                "parent_checkpoint_id": row[3],
                "channel_values": row[4],
                "metadata": row[5],
                "created_at": row[6].isoformat() if row[6] else None,
            }
            for row in rows
        ]

    def save_checkpoint(
        self,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
        parent_checkpoint_id: str | None,
        channel_values: dict[str, Any],
        metadata: dict[str, Any],
    ) -> None:
        """
        Save a checkpoint.

        Args:
            thread_id: The conversation thread ID
            checkpoint_ns: Checkpoint namespace
            checkpoint_id: The checkpoint ID
            parent_checkpoint_id: Parent checkpoint ID (or None)
            channel_values: Serialized channel values
            metadata: Checkpoint metadata
        """
        self.session.execute(
            text(
                """
                INSERT INTO conversation_checkpoints
                (thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id,
                 channel_values, metadata)
                VALUES (:thread_id, :checkpoint_ns, :checkpoint_id, :parent_checkpoint_id,
                        :channel_values, :metadata)
                ON CONFLICT (thread_id, checkpoint_ns, checkpoint_id)
                DO UPDATE SET
                    channel_values = EXCLUDED.channel_values,
                    metadata = EXCLUDED.metadata,
                    created_at = NOW()
                """
            ),
            {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
                "parent_checkpoint_id": parent_checkpoint_id,
                "channel_values": Json(channel_values),
                "metadata": Json(metadata),
            },
        )
        self._pending_commits += 1
        logger.debug(f"Saved checkpoint {checkpoint_id} for thread {thread_id}")

    def delete_thread(self, thread_id: str) -> None:
        """
        Delete all data for a thread.

        Args:
            thread_id: The conversation thread ID
        """
        # Delete messages
        self.session.execute(
            text("DELETE FROM conversation_messages WHERE thread_id = :thread_id"),
            {"thread_id": thread_id},
        )

        # Delete checkpoints
        self.session.execute(
            text("DELETE FROM conversation_checkpoints WHERE thread_id = :thread_id"),
            {"thread_id": thread_id},
        )

        # Delete writes
        self.session.execute(
            text("DELETE FROM conversation_writes WHERE thread_id = :thread_id"),
            {"thread_id": thread_id},
        )

        self._pending_commits += 1
        logger.info(f"Deleted all data for thread {thread_id}")

    def save_write(
        self,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
        task_id: str,
        channel: str,
        value: Any,
    ) -> None:
        """
        Save a pending write.

        Args:
            thread_id: The conversation thread ID
            checkpoint_ns: Checkpoint namespace
            checkpoint_id: The checkpoint ID
            task_id: Task ID
            channel: Channel name
            value: Value to write
        """
        # Convert value to JSON-serializable format
        if isinstance(value, str):
            json_value = value  # psycopg will handle string to JSON conversion
        elif isinstance(value, (dict, list)):
            json_value = Json(value)
        else:
            json_value = json.dumps(value)

        self.session.execute(
            text(
                """
                INSERT INTO conversation_writes
                (thread_id, checkpoint_ns, checkpoint_id, task_id, channel, value)
                VALUES (:thread_id, :checkpoint_ns, :checkpoint_id, :task_id, :channel, to_jsonb(:value))
                ON CONFLICT (thread_id, checkpoint_ns, checkpoint_id, task_id, channel)
                DO UPDATE SET value = EXCLUDED.value, created_at = NOW()
                """
            ),
            {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
                "task_id": task_id,
                "channel": channel,
                "value": json_value,
            },
        )
        self._pending_commits += 1

    def get_writes(
        self,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
    ) -> list[dict[str, Any]]:
        """
        Get pending writes for a checkpoint.

        Args:
            thread_id: The conversation thread ID
            checkpoint_ns: Checkpoint namespace
            checkpoint_id: The checkpoint ID

        Returns:
            List of write dicts
        """
        result = self.session.execute(
            text(
                """
                SELECT task_id, channel, value, created_at
                FROM conversation_writes
                WHERE thread_id = :thread_id
                  AND checkpoint_ns = :checkpoint_ns
                  AND checkpoint_id = :checkpoint_id
                ORDER BY created_at ASC
                """
            ),
            {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            },
        )
        rows = result.fetchall()

        return [
            {
                "task_id": row[0],
                "channel": row[1],
                "value": row[2],
                "created_at": row[3].isoformat() if row[3] else None,
            }
            for row in rows
        ]
