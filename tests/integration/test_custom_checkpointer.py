"""Temporary test to validate CustomCheckpointer serialization round-trip.

Verifies that pending_writes values survive a put_writes -> get_tuple cycle,
and that a simple LangGraph graph executes nodes correctly when using the
custom checkpointer (the actual bug: graph was skipping node execution
because pending_writes were returned as raw serialized blobs instead of
deserialized LangGraph objects).
"""

import uuid
from typing import Annotated, Any
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import Checkpoint, CheckpointMetadata
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from agent.custom_checkpointer import (
    CustomCheckpointer,
)

# ── Minimal graph state for testing ──────────────────────────────────────


class MiniState(TypedDict):
    messages: Annotated[list[Any], add_messages]
    was_node_called: bool


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def checkpointer():
    """Create a CustomCheckpointer backed by a mock repository.

    Mocks the database layer so we can test serialization logic in isolation
    without needing a running Postgres instance.
    """
    cp = CustomCheckpointer()

    # In-memory storage that simulates the DB
    stored_checkpoints: dict[tuple[str, str, str], dict[str, Any]] = {}
    stored_writes: dict[tuple[str, str, str], list[dict[str, Any]]] = {}

    def mock_save_checkpoint(
        thread_id,
        checkpoint_ns,
        checkpoint_id,
        parent_checkpoint_id,
        channel_values,
        metadata,
    ):
        # psycopg Json wrapper — extract the adapted value
        cv = channel_values.obj if hasattr(channel_values, "obj") else channel_values
        md = metadata.obj if hasattr(metadata, "obj") else metadata
        stored_checkpoints[(thread_id, checkpoint_ns, checkpoint_id)] = {
            "thread_id": thread_id,
            "checkpoint_ns": checkpoint_ns,
            "checkpoint_id": checkpoint_id,
            "parent_checkpoint_id": parent_checkpoint_id,
            "channel_values": cv,
            "metadata": md,
            "created_at": None,
        }

    def mock_get_latest_checkpoint(thread_id, checkpoint_ns=""):
        matches = [
            v for k, v in stored_checkpoints.items() if k[0] == thread_id and k[1] == checkpoint_ns
        ]
        return matches[-1] if matches else None

    def mock_get_checkpoint(thread_id, checkpoint_ns, checkpoint_id):
        return stored_checkpoints.get((thread_id, checkpoint_ns, checkpoint_id))

    def mock_save_write(
        thread_id,
        checkpoint_ns,
        checkpoint_id,
        task_id,
        channel,
        value,
    ):
        from psycopg.types.json import Json

        # Simulate what the repo does: Json wraps dicts/lists, json.dumps others
        if isinstance(value, Json):
            stored_val = value.obj
        elif isinstance(value, str):
            stored_val = value
        else:
            import json

            stored_val = json.loads(value) if isinstance(value, str) else value

        key = (thread_id, checkpoint_ns, checkpoint_id)
        if key not in stored_writes:
            stored_writes[key] = []
        # Replace existing write for same task_id+channel
        stored_writes[key] = [
            w
            for w in stored_writes[key]
            if not (w["task_id"] == task_id and w["channel"] == channel)
        ]
        stored_writes[key].append(
            {
                "task_id": task_id,
                "channel": channel,
                "value": stored_val,
                "created_at": None,
            }
        )

    def mock_get_writes(thread_id, checkpoint_ns, checkpoint_id):
        return stored_writes.get((thread_id, checkpoint_ns, checkpoint_id), [])

    def mock_commit():
        pass

    def mock_add_message(*args, **kwargs):
        return 1

    # Wire up the mock repository
    mock_repo = MagicMock()
    mock_repo.save_checkpoint = mock_save_checkpoint
    mock_repo.get_latest_checkpoint = mock_get_latest_checkpoint
    mock_repo.get_checkpoint = mock_get_checkpoint
    mock_repo.save_write = mock_save_write
    mock_repo.get_writes = mock_get_writes
    mock_repo.commit = mock_commit
    mock_repo.add_message = mock_add_message

    cp._get_repo = lambda: mock_repo

    return cp


# ── Tests ────────────────────────────────────────────────────────────────


def test_pending_writes_round_trip(checkpointer):
    """Verify that put_writes values are correctly deserialized by get_tuple.

    This is the core bug: put_writes serializes values via _serialize_for_storage,
    but get_tuple was returning the raw serialized form instead of deserializing.
    """
    thread_id = f"test-thread-{uuid.uuid4().hex[:8]}"
    checkpoint_id = str(uuid.uuid4())

    # Store a checkpoint first (required before put_writes)
    checkpoint: Checkpoint = {
        "v": 1,
        "id": checkpoint_id,
        "ts": "2026-02-15T00:00:00+00:00",
        "channel_values": {"messages": []},
        "channel_versions": {},
        "versions_seen": {},
        "updated_channels": None,
    }
    metadata: CheckpointMetadata = {
        "source": "input",
        "step": 0,
        "parents": {},
    }

    config = checkpointer.put(
        config=RunnableConfig(configurable={"thread_id": thread_id, "checkpoint_ns": ""}),
        checkpoint=checkpoint,
        metadata=metadata,
        new_versions={},
    )

    # Store a pending write with a LangChain message object
    original_message = AIMessage(content="Hello from the supervisor")
    checkpointer.put_writes(
        config=config,
        writes=[("messages", original_message)],
        task_id="test-task-1",
    )

    # Now read it back via get_tuple
    result = checkpointer.get_tuple({"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}})

    assert result is not None
    assert result.pending_writes is not None
    assert len(result.pending_writes) == 1

    task_id, channel, value = result.pending_writes[0]
    assert task_id == "test-task-1"
    assert channel == "messages"

    # The critical assertion: value should be a deserialized AIMessage,
    # not a raw [format_type, base64_string] list
    assert isinstance(value, AIMessage), (
        f"Expected AIMessage but got {type(value).__name__}: {value!r}. "
        "This means pending_writes values are not being deserialized in get_tuple."
    )
    assert value.content == "Hello from the supervisor"


def test_graph_executes_node_with_checkpointer(checkpointer):
    """Verify a LangGraph graph actually executes nodes when using the checkpointer.

    This reproduces the production bug: when a message is sent to an existing
    thread, the graph should run the entry node. With the broken checkpointer,
    the graph was loading corrupted pending_writes and skipping node execution.
    """
    node_call_count = {"value": 0}

    def my_node(state: MiniState):
        node_call_count["value"] += 1
        return {
            "messages": [AIMessage(content=f"Response #{node_call_count['value']}")],
            "was_node_called": True,
        }

    # Build a minimal graph
    workflow = StateGraph(MiniState)
    workflow.add_node("agent", my_node)
    workflow.set_entry_point("agent")
    graph = workflow.compile(checkpointer=checkpointer)

    thread_id = f"test-thread-{uuid.uuid4().hex[:8]}"
    config = RunnableConfig(configurable={"thread_id": thread_id})

    # First invocation — should call the node
    result1 = graph.invoke(
        {"messages": [HumanMessage(content="Hello")], "was_node_called": False},
        config=config,
    )
    assert node_call_count["value"] == 1
    assert result1["was_node_called"] is True

    # Second invocation on the SAME thread — this is where the bug manifested.
    # With broken pending_writes deserialization, the graph would skip execution.
    result2 = graph.invoke(
        {"messages": [HumanMessage(content="Follow up question")], "was_node_called": False},
        config=config,
    )
    assert node_call_count["value"] == 2, (
        f"Expected node to be called twice but was called {node_call_count['value']} times. "
        "The graph skipped node execution on the second invocation — "
        "likely due to corrupted pending_writes from the checkpointer."
    )
    assert result2["was_node_called"] is True
