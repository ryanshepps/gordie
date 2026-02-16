"""Async custom checkpointer for LangGraph using our own database schema."""

import asyncio
from collections.abc import AsyncIterator, Iterator, Sequence
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)
from langgraph.checkpoint.serde.base import SerializerProtocol
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from agent.custom_checkpointer import CustomCheckpointer
from module.logger import get_logger

logger = get_logger(__name__)


class AsyncCustomCheckpointer(BaseCheckpointSaver[str]):
    """
    Async version of the custom checkpointer.

    Wraps the synchronous CustomCheckpointer using asyncio.to_thread
    for database operations.
    """

    def __init__(
        self,
        serde: SerializerProtocol | None = None,
    ):
        """Initialize the async custom checkpointer."""
        super().__init__(serde=serde or JsonPlusSerializer())
        self._sync_checkpointer: CustomCheckpointer | None = None

    def _get_sync_checkpointer(self) -> CustomCheckpointer:
        """Get or create the sync checkpointer."""
        if self._sync_checkpointer is None:
            self._sync_checkpointer = CustomCheckpointer(serde=self.serde)
        return self._sync_checkpointer

    async def setup(self) -> None:
        """
        Setup the database tables.

        Note: Tables should be created via Alembic migration.
        This method is called for compatibility with LangGraph's interface.
        """
        # Run setup in thread
        await asyncio.to_thread(self._get_sync_checkpointer().setup)

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        """
        Async version of get_tuple.

        Args:
            config: RunnableConfig with thread_id and optional checkpoint_id

        Returns:
            CheckpointTuple or None if not found
        """
        return await asyncio.to_thread(self._get_sync_checkpointer().get_tuple, config)

    async def alist(
        self,
        config: RunnableConfig | None = None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        """
        Async version of list.

        Args:
            config: RunnableConfig with thread_id
            filter: Optional filter criteria
            before: Only return checkpoints before this config
            limit: Maximum number of checkpoints to return

        Yields:
            CheckpointTuple objects
        """

        # Get list in thread
        def _list_checkpoints():
            return list(
                self._get_sync_checkpointer().list(
                    config=config,  # type: ignore[arg-type]
                    filter=filter,
                    before=before,
                    limit=limit,
                )
            )

        checkpoints = await asyncio.to_thread(_list_checkpoints)

        for checkpoint in checkpoints:
            yield checkpoint

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """
        Async version of put.

        Args:
            config: RunnableConfig with thread_id
            checkpoint: The checkpoint data to store
            metadata: Checkpoint metadata
            new_versions: New channel versions

        Returns:
            Updated config with checkpoint_id
        """
        return await asyncio.to_thread(
            self._get_sync_checkpointer().put,
            config,
            checkpoint,
            metadata,
            new_versions,
        )

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """
        Async version of put_writes.

        Args:
            config: RunnableConfig with thread_id and checkpoint_id
            writes: Sequence of (channel, value) tuples
            task_id: Task ID
            task_path: Task path
        """
        await asyncio.to_thread(
            self._get_sync_checkpointer().put_writes,
            config,
            writes,
            task_id,
            task_path,
        )

    async def adelete_thread(self, thread_id: str) -> None:
        """
        Async version of delete_thread.

        Args:
            thread_id: The thread ID to delete
        """
        await asyncio.to_thread(self._get_sync_checkpointer().delete_thread, thread_id)

    async def add_message(
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
        return await asyncio.to_thread(
            self._get_sync_checkpointer().add_message,
            thread_id,
            content,
            role,
            message_type,
            metadata,
        )

    # Sync methods (required by BaseCheckpointSaver interface)
    # These delegate to the sync checkpointer

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        """Sync version - delegates to sync checkpointer."""
        return self._get_sync_checkpointer().get_tuple(config)

    def list(
        self,
        config: RunnableConfig | None = None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        """Sync version - delegates to sync checkpointer."""
        return self._get_sync_checkpointer().list(
            config=config,
            filter=filter,
            before=before,
            limit=limit,
        )

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Sync version - delegates to sync checkpointer."""
        return self._get_sync_checkpointer().put(
            config,
            checkpoint,
            metadata,
            new_versions,
        )

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """Sync version - delegates to sync checkpointer."""
        return self._get_sync_checkpointer().put_writes(
            config,
            writes,
            task_id,
            task_path,
        )

    def delete_thread(self, thread_id: str) -> None:
        """Sync version - delegates to sync checkpointer."""
        return self._get_sync_checkpointer().delete_thread(thread_id)

    def get_next_version(
        self,
        current: str | None,
        channel: str | None = None,
    ) -> str:
        """Get next version - delegates to sync checkpointer."""
        return self._get_sync_checkpointer().get_next_version(current, channel)
