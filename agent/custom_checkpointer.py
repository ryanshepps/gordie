"""Custom checkpointer for LangGraph using our own database schema."""

import base64
import threading
from collections.abc import Iterator, Sequence
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    get_checkpoint_id,
)
from langgraph.checkpoint.serde.base import SerializerProtocol
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from data.conversation_repository import ConversationRepository
from module.logger import get_logger

logger = get_logger(__name__)

# Thread-local storage for repository instances
_thread_local = threading.local()


def _serialize_for_storage(data: Any, serde: SerializerProtocol) -> Any:
    """
    Serialize data for storage in PostgreSQL JSONB.

    Uses the serde to handle LangChain objects, then converts to JSON-compatible format.
    """
    format_type, bytes_data = serde.dumps_typed(data)
    # Convert bytes to base64-encoded string for JSON compatibility
    return [format_type, base64.b64encode(bytes_data).decode("utf-8")]


def _deserialize_from_storage(data: Any, serde: SerializerProtocol) -> Any:
    """
    Deserialize data from PostgreSQL JSONB storage format.

    Decodes base64 and uses the serde to restore LangChain objects.
    """
    if isinstance(data, list) and len(data) == 2:
        format_type, b64_data = data
        if isinstance(b64_data, str):
            try:
                bytes_data = base64.b64decode(b64_data)
                return serde.loads_typed((format_type, bytes_data))
            except Exception:
                # If deserialization fails, return as-is
                pass
    return data


class CustomCheckpointer(BaseCheckpointSaver[str]):
    """
    Custom checkpointer that stores conversation data in our own tables.

    This provides:
    - Direct access to message history for web view
    - Ability to add out-of-band messages (auto-acks)
    - Clean separation of conversation data from LangGraph internals
    """

    def __init__(
        self,
        serde: SerializerProtocol | None = None,
    ):
        """Initialize the custom checkpointer."""
        super().__init__(serde=serde or JsonPlusSerializer())

    def _get_repo(self) -> ConversationRepository:
        """Get or create the conversation repository for the current thread."""
        # Use thread-local storage to ensure each thread has its own session
        if not hasattr(_thread_local, "repo") or _thread_local.repo is None:
            _thread_local.repo = ConversationRepository()
        return _thread_local.repo

    def setup(self) -> None:
        """
        Setup the database tables.

        Note: Tables should be created via Alembic migration.
        This method is called for compatibility with LangGraph's interface.
        """
        logger.info("CustomCheckpointer setup complete (tables managed by Alembic)")

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        """
        Get a checkpoint tuple by config.

        Args:
            config: RunnableConfig with thread_id and optional checkpoint_id

        Returns:
            CheckpointTuple or None if not found
        """
        configurable = config.get("configurable", {})
        thread_id = configurable["thread_id"]
        checkpoint_ns = configurable.get("checkpoint_ns", "")
        checkpoint_id = get_checkpoint_id(config)

        repo = self._get_repo()

        if checkpoint_id:
            # Get specific checkpoint
            checkpoint_data = repo.get_checkpoint(thread_id, checkpoint_ns, checkpoint_id)
        else:
            # Get latest checkpoint
            checkpoint_data = repo.get_latest_checkpoint(thread_id, checkpoint_ns)

        if not checkpoint_data:
            return None

        # Get pending writes
        writes = repo.get_writes(
            thread_id,
            checkpoint_data["checkpoint_ns"],
            checkpoint_data["checkpoint_id"],
        )

        # Build parent config
        parent_config: RunnableConfig | None = None
        if checkpoint_data.get("parent_checkpoint_id"):
            parent_config = {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": checkpoint_data["parent_checkpoint_id"],
                }
            }

        # Convert writes to pending_writes format, deserializing values
        pending_writes = (
            [
                (
                    write["task_id"],
                    write["channel"],
                    _deserialize_from_storage(write["value"], self.serde),
                )
                for write in writes
            ]
            if writes
            else None
        )

        # Deserialize checkpoint and metadata
        checkpoint_dict = _deserialize_from_storage(checkpoint_data["channel_values"], self.serde)
        metadata_dict = _deserialize_from_storage(checkpoint_data["metadata"], self.serde)

        return CheckpointTuple(
            config={
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_data["checkpoint_ns"],
                    "checkpoint_id": checkpoint_data["checkpoint_id"],
                }
            },
            checkpoint=checkpoint_dict,
            metadata=metadata_dict,
            parent_config=parent_config,
            pending_writes=pending_writes,
        )

    def list(
        self,
        config: RunnableConfig | None = None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        """
        List checkpoints for a thread.

        Args:
            config: RunnableConfig with thread_id
            filter: Optional filter criteria
            before: Only return checkpoints before this config
            limit: Maximum number of checkpoints to return

        Yields:
            CheckpointTuple objects
        """
        configurable = config.get("configurable", {}) if config else {}
        thread_id = configurable.get("thread_id") if config else None
        checkpoint_ns = configurable.get("checkpoint_ns", "") if config else ""

        if not thread_id:
            return

        repo = self._get_repo()
        checkpoints = repo.list_checkpoints(thread_id, checkpoint_ns, limit=limit)

        # Filter by before if provided
        before_checkpoint_id = None
        if before:
            before_checkpoint_id = before.get("configurable", {}).get("checkpoint_id")

        for checkpoint_data in checkpoints:
            # Skip if we've reached the before checkpoint
            if before_checkpoint_id and checkpoint_data["checkpoint_id"] == before_checkpoint_id:
                break

            # Get pending writes
            writes = repo.get_writes(
                thread_id,
                checkpoint_data["checkpoint_ns"],
                checkpoint_data["checkpoint_id"],
            )

            # Build parent config
            parent_config: RunnableConfig | None = None
            if checkpoint_data.get("parent_checkpoint_id"):
                parent_config = {
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": checkpoint_data["parent_checkpoint_id"],
                    }
                }

            # Convert writes to pending_writes format, deserializing values
            pending_writes = (
                [
                    (
                        write["task_id"],
                        write["channel"],
                        _deserialize_from_storage(write["value"], self.serde),
                    )
                    for write in writes
                ]
                if writes
                else None
            )

            # Deserialize checkpoint and metadata
            checkpoint_dict = _deserialize_from_storage(
                checkpoint_data["channel_values"], self.serde
            )
            metadata_dict = _deserialize_from_storage(checkpoint_data["metadata"], self.serde)

            yield CheckpointTuple(
                config={
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_data["checkpoint_ns"],
                        "checkpoint_id": checkpoint_data["checkpoint_id"],
                    }
                },
                checkpoint=checkpoint_dict,
                metadata=metadata_dict,
                parent_config=parent_config,
                pending_writes=pending_writes,
            )

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """
        Store a checkpoint.

        Args:
            config: RunnableConfig with thread_id
            checkpoint: The checkpoint data to store
            metadata: Checkpoint metadata
            new_versions: New channel versions

        Returns:
            Updated config with checkpoint_id
        """
        configurable = config.get("configurable", {})
        thread_id = configurable["thread_id"]
        checkpoint_ns = configurable.get("checkpoint_ns", "")
        checkpoint_id = checkpoint["id"]

        # The parent checkpoint ID is the checkpoint_id from the incoming config
        # (LangGraph passes the previous checkpoint's config when calling put)
        parent_checkpoint_id = configurable.get("checkpoint_id")

        repo = self._get_repo()

        # Serialize checkpoint data for storage
        checkpoint_storage = _serialize_for_storage(checkpoint, self.serde)
        metadata_storage = _serialize_for_storage(metadata, self.serde)

        # Save checkpoint
        repo.save_checkpoint(
            thread_id=thread_id,
            checkpoint_ns=checkpoint_ns,
            checkpoint_id=checkpoint_id,
            parent_checkpoint_id=parent_checkpoint_id,
            channel_values=checkpoint_storage,
            metadata=metadata_storage,
        )

        # Commit all pending transactions
        repo.commit()

        # Return updated config
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """
        Store intermediate writes.

        Args:
            config: RunnableConfig with thread_id and checkpoint_id
            writes: Sequence of (channel, value) tuples
            task_id: Task ID
            task_path: Task path
        """
        configurable = config.get("configurable", {})
        thread_id = configurable["thread_id"]
        checkpoint_ns = configurable.get("checkpoint_ns", "")
        checkpoint_id = configurable["checkpoint_id"]

        repo = self._get_repo()

        for channel, value in writes:
            # Serialize value for storage
            serialized_value = _serialize_for_storage(value, self.serde)

            repo.save_write(
                thread_id=thread_id,
                checkpoint_ns=checkpoint_ns,
                checkpoint_id=checkpoint_id,
                task_id=task_id,
                channel=channel,
                value=serialized_value,
            )

        # Commit all pending transactions
        repo.commit()

    def delete_thread(self, thread_id: str) -> None:
        """
        Delete all data for a thread.

        Args:
            thread_id: The thread ID to delete
        """
        repo = self._get_repo()
        repo.delete_thread(thread_id)
        repo.commit()

    def add_message(
        self,
        thread_id: str,
        content: str,
        role: str = "ai",
        message_type: str = "auto_ack",
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """
        Add a message to the conversation outside of normal checkpoint flow.

        This is the key feature for auto-acknowledgments - it allows adding
        messages mid-processing that will appear in the web view.

        Args:
            thread_id: The conversation thread ID
            content: Message content
            role: Message role ('human', 'ai', or 'system')
            message_type: Type of message ('standard', 'auto_ack', 'status')
            metadata: Optional metadata

        Returns:
            The ID of the inserted message
        """
        # Get the latest checkpoint ID for this thread
        repo = self._get_repo()
        latest = repo.get_latest_checkpoint(thread_id)
        checkpoint_id = latest["checkpoint_id"] if latest else "out-of-band"

        # Add the message
        message_id = repo.add_message(
            thread_id=thread_id,
            checkpoint_id=checkpoint_id,
            role=role,
            content=content,
            message_type=message_type,
            metadata=metadata,
        )

        # Commit the transaction
        repo.commit()

        logger.info(f"Added {message_type} message to thread {thread_id}: {content[:50]}...")
        return message_id

    def get_next_version(
        self,
        current: str | None,
        channel: str | None = None,
    ) -> str:
        """
        Generate the next version ID for a channel.

        LangGraph compares versions using string ordering to determine which
        channels have been updated. Versions must be monotonically increasing
        strings — a zero-padded integer counter matching MemorySaver's format.

        Args:
            current: Current version ID or None
            channel: Channel name

        Returns:
            New version ID (monotonically increasing string)
        """
        import random

        current_int = 0 if current is None else int(current.split(".")[0])
        next_int = current_int + 1
        return f"{next_int:032d}.{random.random()}"
