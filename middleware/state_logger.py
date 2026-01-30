"""Middleware for logging AgentState at key points in the agent flow."""

import time
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import AgentState as BaseAgentState
from langgraph.runtime import Runtime
from opentelemetry import trace

from module.logger import get_logger
from module.metrics import agent_execution_duration_seconds, agent_invocations_total
from module.tracing import create_span, get_current_span, set_span_ok

logger = get_logger(__name__)

# Type alias for the base AgentState with Any response type
_BaseState = BaseAgentState[Any]


def _format_state(state: _BaseState) -> str:
    """Format AgentState dict into a readable log string."""
    # Fields to skip (too verbose or not useful)
    skip_fields = {"messages", "user_teams", "persona"}

    state_parts = []
    for field, value in state.items():
        if field in skip_fields or value is None:
            continue

        # Truncate long strings
        if isinstance(value, str) and len(value) > 50:
            value = value[:50] + "..."
        elif isinstance(value, list) and len(value) > 5:
            value = f"[{len(value)} items]"

        state_parts.append(f"{field}={value}")

    return ", ".join(state_parts) if state_parts else "empty_state"


class StateLoggingMiddleware(AgentMiddleware[_BaseState, Any]):
    """Middleware that logs AgentState before and after model calls."""

    def __init__(self, agent_name: str = "agent"):
        """
        Initialize the middleware.

        Args:
            agent_name: Name to identify which agent is logging (e.g., "controller", "onboarding")
        """
        self.agent_name = agent_name
        self.start_time = None
        self._agent_span: trace.Span | None = None
        self._span_context = None

    def before_model(self, state: _BaseState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        """Log state before each model call."""
        state_str = _format_state(state)
        logger.info(
            f"[{self.agent_name}:BEFORE_MODEL] {state_str}", extra={"agent_name": self.agent_name}
        )

        current_span = get_current_span()
        if current_span.is_recording():
            current_span.add_event(
                "model_call_started",
                {"agent_name": self.agent_name},
            )

        return None

    def after_model(self, state: _BaseState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        """Log state after each model call, including reasoning and tool decisions."""
        state_str = _format_state(state)
        logger.info(
            f"[{self.agent_name}:AFTER_MODEL] {state_str}", extra={"agent_name": self.agent_name}
        )

        # Log agent reasoning from the latest AI message
        messages = state.get("messages", [])
        tool_decisions = []
        if messages:
            last_message = messages[-1]

            # Log the agent's thinking/reasoning (the content of its response)
            if hasattr(last_message, "content") and last_message.content:
                content = last_message.content
                # Truncate long content for readability
                if isinstance(content, str) and len(content) > 500:
                    content = content[:500] + "..."
                logger.info(
                    f"[{self.agent_name}:THINKING] {content}",
                    extra={"agent_name": self.agent_name},
                )

            # Log tool call decisions (only AIMessage has tool_calls)
            tool_calls = getattr(last_message, "tool_calls", None)
            if tool_calls:
                for tool_call in tool_calls:
                    tool_name = tool_call.get("name", "unknown")
                    tool_args = tool_call.get("args", {})
                    tool_decisions.append(tool_name)
                    # Truncate long args for readability
                    args_str = str(tool_args)
                    if len(args_str) > 300:
                        args_str = args_str[:300] + "..."
                    logger.info(
                        f"[{self.agent_name}:TOOL_DECISION] "
                        f"Calling '{tool_name}' with args: {args_str}",
                        extra={"agent_name": self.agent_name, "tool_name": tool_name},
                    )

        current_span = get_current_span()
        if current_span.is_recording():
            event_attrs = {"agent_name": self.agent_name}
            if tool_decisions:
                event_attrs["tools_called"] = ",".join(tool_decisions)
            current_span.add_event("model_call_completed", event_attrs)

        return None

    def before_agent(self, state: _BaseState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        """Log state when agent execution starts."""
        self.start_time = time.time()
        state_str = _format_state(state)

        user_email = state.get("user_email", "unknown")

        self._span_context = create_span(
            f"agent.{self.agent_name}",
            {
                "agent_name": self.agent_name,
                "user_email": user_email,
            },
        )
        self._agent_span = self._span_context.__enter__()

        logger.info(
            f"[{self.agent_name}:AGENT_START] {state_str}",
            extra={"agent_name": self.agent_name, "user_email": user_email},
        )
        return None

    def after_agent(self, state: _BaseState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        """Log state when agent execution completes."""
        duration = time.time() - self.start_time if self.start_time else 0
        state_str = _format_state(state)

        user_email = state.get("user_email", "unknown")

        status = "success" if state.get("response") else "error"
        agent_invocations_total.labels(agent_name=self.agent_name, status=status).inc()
        agent_execution_duration_seconds.labels(agent_name=self.agent_name).observe(duration)

        if self._agent_span is not None:
            self._agent_span.set_attribute("duration_ms", duration * 1000)
            self._agent_span.set_attribute("status", status)

            if status == "success":
                set_span_ok(self._agent_span)
            else:
                self._agent_span.set_status(
                    trace.Status(trace.StatusCode.ERROR, "Agent execution failed")
                )

            if self._span_context is not None:
                self._span_context.__exit__(None, None, None)
                self._span_context = None
            self._agent_span = None

        logger.info(
            f"[{self.agent_name}:AGENT_END] {state_str}",
            extra={
                "agent_name": self.agent_name,
                "user_email": user_email,
                "duration_ms": duration * 1000,
                "status": status,
            },
        )
        return None
