"""Routing evals for notification requests.

Verify the supervisor LLM routes notification requests to the manage_notifications
tool with the correct arguments. These invoke the real LLM, so they are
non-deterministic and should be treated as evals, not unit tests.
"""

from typing import Any, cast

import pytest
from langchain_core.messages import HumanMessage

from agent.agent_state import AgentState
from agent.SupervisorAgent import supervisor_node
from tests.evals.conftest import extract_tool_calls_from_messages, retry_on_rate_limit


@pytest.mark.integration
class TestNotificationRouting:
    """Test that notification requests route to manage_notifications tool."""

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_stop_digest_routes_correctly(
        self,
        mock_user_state: AgentState,
        mock_yahoo_tools: dict[str, Any],
    ) -> None:
        """'Stop sending me weekly digests' routes to manage_notifications with enabled=False."""
        mock_user_state["messages"] = [
            HumanMessage(content="Stop sending me weekly digests")
        ]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        result_messages = cast(dict[str, Any], update).get("messages", [])
        tool_calls = extract_tool_calls_from_messages(result_messages)

        notification_calls = [
            tc for tc in tool_calls if tc["name"] == "manage_notifications"
        ]

        assert len(notification_calls) >= 1, (
            f"Expected manage_notifications tool call, got: "
            f"{[tc['name'] for tc in tool_calls]}"
        )

        call_args = notification_calls[0]["args"]
        assert call_args.get("enabled") is False, (
            f"Expected enabled=False, got: {call_args}"
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_unsubscribe_routes_correctly(
        self,
        mock_user_state: AgentState,
        mock_yahoo_tools: dict[str, Any],
    ) -> None:
        """'Unsubscribe from the weekly emails' routes to manage_notifications with enabled=False."""
        mock_user_state["messages"] = [
            HumanMessage(content="Unsubscribe from the weekly emails")
        ]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        result_messages = cast(dict[str, Any], update).get("messages", [])
        tool_calls = extract_tool_calls_from_messages(result_messages)

        notification_calls = [
            tc for tc in tool_calls if tc["name"] == "manage_notifications"
        ]

        assert len(notification_calls) >= 1, (
            f"Expected manage_notifications tool call for unsubscribe request, got: "
            f"{[tc['name'] for tc in tool_calls]}"
        )

        call_args = notification_calls[0]["args"]
        assert call_args.get("enabled") is False, (
            f"Expected enabled=False for unsubscribe, got: {call_args}"
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_turn_on_digest_routes_correctly(
        self,
        mock_user_state: AgentState,
        mock_yahoo_tools: dict[str, Any],
    ) -> None:
        """'Turn the weekly digest back on' routes to manage_notifications with enabled=True."""
        mock_user_state["messages"] = [
            HumanMessage(content="Turn the weekly digest back on")
        ]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        result_messages = cast(dict[str, Any], update).get("messages", [])
        tool_calls = extract_tool_calls_from_messages(result_messages)

        notification_calls = [
            tc for tc in tool_calls if tc["name"] == "manage_notifications"
        ]

        assert len(notification_calls) >= 1, (
            f"Expected manage_notifications tool call for enable request, got: "
            f"{[tc['name'] for tc in tool_calls]}"
        )

        call_args = notification_calls[0]["args"]
        assert call_args.get("enabled") is True, (
            f"Expected enabled=True for re-enable request, got: {call_args}"
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_notification_tool_receives_correct_user_email(
        self,
        mock_user_state: AgentState,
        mock_yahoo_tools: dict[str, Any],
    ) -> None:
        """manage_notifications receives the correct user_email from state."""
        mock_user_state["messages"] = [
            HumanMessage(content="Stop sending me the weekly digest")
        ]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        result_messages = cast(dict[str, Any], update).get("messages", [])
        tool_calls = extract_tool_calls_from_messages(result_messages)

        notification_calls = [
            tc for tc in tool_calls if tc["name"] == "manage_notifications"
        ]

        assert len(notification_calls) >= 1, (
            f"Expected manage_notifications tool call, got: "
            f"{[tc['name'] for tc in tool_calls]}"
        )
        call_args = notification_calls[0]["args"]
        assert call_args.get("user_email") == "test@example.com", (
            f"Expected user_email='test@example.com', got: {call_args}"
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_notification_tool_receives_correct_league_id(
        self,
        mock_user_state: AgentState,
        mock_yahoo_tools: dict[str, Any],
    ) -> None:
        """manage_notifications receives the correct league_id from state."""
        mock_user_state["messages"] = [
            HumanMessage(content="Please turn off the weekly digest")
        ]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        result_messages = cast(dict[str, Any], update).get("messages", [])
        tool_calls = extract_tool_calls_from_messages(result_messages)

        notification_calls = [
            tc for tc in tool_calls if tc["name"] == "manage_notifications"
        ]

        assert len(notification_calls) >= 1, (
            f"Expected manage_notifications tool call, got: "
            f"{[tc['name'] for tc in tool_calls]}"
        )
        call_args = notification_calls[0]["args"]
        assert call_args.get("league_id") == "12345", (
            f"Expected league_id='12345', got: {call_args}"
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_notification_tool_uses_weekly_digest_type(
        self,
        mock_user_state: AgentState,
        mock_yahoo_tools: dict[str, Any],
    ) -> None:
        """manage_notifications uses 'weekly_digest' as the notification type."""
        mock_user_state["messages"] = [
            HumanMessage(content="Stop the weekly digest emails")
        ]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        result_messages = cast(dict[str, Any], update).get("messages", [])
        tool_calls = extract_tool_calls_from_messages(result_messages)

        notification_calls = [
            tc for tc in tool_calls if tc["name"] == "manage_notifications"
        ]

        assert len(notification_calls) >= 1, (
            f"Expected manage_notifications tool call, got: "
            f"{[tc['name'] for tc in tool_calls]}"
        )
        call_args = notification_calls[0]["args"]
        assert call_args.get("notification_type") == "weekly_digest", (
            f"Expected notification_type='weekly_digest', got: {call_args}"
        )
