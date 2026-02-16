"""Auto-acknowledgment middleware for long-running agent operations."""

import asyncio
import threading
import time
from collections.abc import Callable, Coroutine
from typing import Any

from agent.checkpointer import checkpointer
from module.logger import get_logger

logger = get_logger(__name__)

# Contextual messages based on request keywords
CONTEXTUAL_MESSAGES = {
    "trade": "Analyzing that trade...",
    "waiver": "Checking waiver wire...",
    "available": "Checking waiver wire...",
    "pickup": "Checking waiver wire...",
    "roster": "Looking at your roster...",
    "lineup": "Looking at your roster...",
    "stats": "Crunching the numbers...",
    "compare": "Crunching the numbers...",
}

DEFAULT_ACK_MESSAGE = "On it! One sec..."


def _extract_phone_from_thread_id(thread_id: str) -> str | None:
    """Extract phone number from SMS thread_id format 'sms:{phone}:{uuid}'."""
    parts = thread_id.split(":")
    if len(parts) >= 3 and parts[0] == "sms":
        return parts[1]
    return None


def _get_contextual_message(user_message: str) -> str:
    """Get contextual acknowledgment message based on user request."""
    message_lower = user_message.lower()
    for keyword, ack_message in CONTEXTUAL_MESSAGES.items():
        if keyword in message_lower:
            return ack_message
    return DEFAULT_ACK_MESSAGE


def _send_sms_ack(phone_number: str, message: str) -> bool:
    """Send an SMS acknowledgment."""
    try:
        from server.sms_service import SmsService

        sms_service = SmsService()
        result = sms_service.send_sms(phone_number, message)

        if result.success:
            logger.info(f"Auto-ack SMS sent to {phone_number}")
            return True
        else:
            logger.error(f"Failed to send auto-ack SMS: {result.error}")
            return False

    except Exception as e:
        logger.error(f"Error sending auto-ack SMS: {e}")
        return False


class AutoAckMiddleware:
    """
    Middleware that sends automatic acknowledgment messages for long-running operations.

    Monitors agent execution time and sends a contextual acknowledgment if processing
    exceeds the configured timeout (default 1000ms). Only sends acks for SMS and Web Chat
    channels - email is skipped since it's inherently asynchronous.

    Prevents duplicate acks using the ack_sent flag in state.
    """

    def __init__(self, timeout_ms: int = 1000):
        """
        Initialize the middleware.

        Args:
            timeout_ms: Timeout in milliseconds before sending auto-ack (default: 1000)
        """
        self.timeout_ms = timeout_ms

    def _should_skip_ack(self, state: dict[str, Any]) -> bool:
        """Check if we should skip sending auto-ack for this request."""
        channel = state.get("channel", "")

        # Skip email channel entirely
        if channel == "email":
            return True

        # Skip if ack already sent
        return bool(state.get("ack_sent", False))

    def _send_ack(self, state: dict[str, Any]) -> None:
        """Send the appropriate acknowledgment based on channel."""
        channel = state.get("channel", "")
        thread_id = state.get("thread_id", "")

        # Get the last user message for contextual ack
        messages = state.get("messages", [])
        user_message = ""
        if messages:
            last_msg = messages[-1]
            if isinstance(last_msg, dict):
                user_message = last_msg.get("content", "")
            elif hasattr(last_msg, "content"):
                user_message = str(last_msg.content)

        ack_message = _get_contextual_message(user_message)

        try:
            if channel == "sms":
                phone_number = _extract_phone_from_thread_id(thread_id)
                if phone_number:
                    success = _send_sms_ack(phone_number, ack_message)
                    if success:
                        # Persist to conversation_messages table so it appears in web view
                        # This is the key feature of the custom checkpointer!
                        checkpointer.add_message(
                            thread_id=thread_id,
                            content=ack_message,
                            role="ai",
                            message_type="auto_ack",
                            metadata={
                                "source": "auto_ack_middleware",
                                "timeout_ms": self.timeout_ms,
                            },
                        )
                else:
                    logger.error(f"Could not extract phone number from thread_id: {thread_id}")

            elif channel == "web" or channel == "web_chat":
                # For web chat, we rely on the streaming mechanism
                # The ack is logged and would need special handling in the stream
                logger.info(f"Web chat auto-ack: {ack_message}")
                # Note: Web chat streaming ack would require additional infrastructure
                # to emit SSE events from outside the normal stream flow

        except Exception as e:
            # Don't let ack errors interrupt the main flow
            logger.error(f"Error sending auto-ack: {e}")

    async def wrap_agent_call(
        self,
        agent_fn: Callable[..., Coroutine[Any, Any, Any]],
        state: dict[str, Any],
        config: dict[str, Any],
    ) -> Any:
        """
        Wrap an async agent call with auto-acknowledgment logic.

        Args:
            agent_fn: The async agent function to wrap (e.g., agent.ainvoke or agent.astream)
            state: The agent state dictionary
            config: The runnable configuration

        Returns:
            The result of the agent function call
        """
        if self._should_skip_ack(state):
            # Skip middleware - just call the agent directly
            return await agent_fn(state, config)

        # Record processing start time
        state["processing_start_time"] = time.monotonic()

        # Create the agent task
        agent_task = asyncio.create_task(agent_fn(state, config))

        # Wait for either completion or timeout
        timeout_seconds = self.timeout_ms / 1000.0
        done, _pending = await asyncio.wait(
            [agent_task],
            timeout=timeout_seconds,
            return_when=asyncio.FIRST_COMPLETED,
        )

        if not done:
            # Agent is still running after timeout - send ack
            logger.info(f"Agent execution exceeded {self.timeout_ms}ms, sending auto-ack")
            self._send_ack(state)
            state["ack_sent"] = True

        # Return the actual result (may still be processing)
        return await agent_task

    def wrap_sync_agent_call(
        self,
        agent_fn: Callable[..., Any],
        state: dict[str, Any],
        config: dict[str, Any],
    ) -> Any:
        """
        Wrap a synchronous agent call with auto-acknowledgment logic.

        Uses a background timer thread to send the ack after the timeout
        while the main agent processing continues. This provides true async
        behavior for sync SMS processing.

        Args:
            agent_fn: The sync agent function to wrap (e.g., agent.invoke)
            state: The agent state dictionary
            config: The runnable configuration

        Returns:
            The result of the agent function call
        """
        if self._should_skip_ack(state):
            # Skip middleware - just call the agent directly
            return agent_fn(state, config)

        # Record processing start time
        state["processing_start_time"] = time.monotonic()

        # Use a threading Event to signal when agent completes
        agent_complete_event = threading.Event()
        ack_sent_flag = {"sent": False}

        def ack_timer():
            """Timer that sends ack after timeout if agent hasn't completed."""
            # Wait for timeout or agent completion
            completed = agent_complete_event.wait(timeout=self.timeout_ms / 1000.0)

            if not completed and not ack_sent_flag["sent"]:
                # Agent is still running after timeout - send ack
                logger.info(f"Agent execution exceeded {self.timeout_ms}ms, sending auto-ack")
                self._send_ack(state)
                ack_sent_flag["sent"] = True
                state["ack_sent"] = True

        # Start the ack timer in a background thread
        timer_thread = threading.Thread(target=ack_timer, daemon=True)
        timer_thread.start()

        try:
            # Run the agent synchronously
            result = agent_fn(state, config)
        finally:
            # Signal that agent is complete
            agent_complete_event.set()
            # Wait for timer thread to finish (it may have already sent the ack)
            timer_thread.join(timeout=0.1)

        return result
