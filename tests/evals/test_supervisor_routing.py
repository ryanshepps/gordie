"""Routing evals for supervisor agent.

These tests verify that the supervisor LLM correctly routes requests to the
appropriate tools/subagents. They invoke the real LLM, so they are
non-deterministic and should be treated as evals, not unit tests.
"""

from typing import Any, cast

import pytest
from langchain_core.messages import HumanMessage

from agent.agent_state import AgentState
from agent.SupervisorAgent import supervisor_node
from tests.evals.conftest import extract_tool_calls_from_messages, retry_on_rate_limit


@pytest.mark.integration
class TestPlayerDropRouting:
    """Test that player drop requests route to appropriate tools."""

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_uses_subagents_for_drop_decision(
        self,
        mock_user_state: AgentState,
        mock_yahoo_tools: dict[str, Any],
    ) -> None:
        """Verify agent delegates to subagents for drop decisions."""
        mock_user_state["messages"] = [HumanMessage(content="Should I drop Timo Meier?")]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        result_messages = cast(dict[str, Any], update).get("messages", [])
        tool_calls = extract_tool_calls_from_messages(result_messages)
        tool_names = [tc["name"] for tc in tool_calls]

        uses_subagents = any(
            tool in tool_names
            for tool in ["trade", "available_players"]
        )

        assert uses_subagents, f"Expected 'trade' or 'available_players' subagent, got: {tool_names}"


@pytest.mark.integration
class TestTradeRouting:
    """Test that trade requests route to the trade subagent."""

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_delegates_to_trade_subagent(
        self,
        mock_user_state: AgentState,
        mock_yahoo_tools: dict[str, Any],
    ) -> None:
        """Verify the agent delegates trade requests to the trade sub-agent."""
        mock_user_state["messages"] = [
            HumanMessage(content="I want to trade away Draisaitl, who should I target?")
        ]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        result_messages = cast(dict[str, Any], update).get("messages", [])
        tool_calls = extract_tool_calls_from_messages(result_messages)
        tool_names = [tc["name"] for tc in tool_calls]

        assert "trade" in tool_names, f"Expected 'trade' in tool calls, got: {tool_names}"

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_uses_trade_subagent_for_undervalued_request(
        self,
        mock_user_state: AgentState,
        mock_yahoo_tools: dict[str, Any],
    ) -> None:
        """Verify the agent uses trade subagent for finding undervalued trade targets."""
        mock_user_state["messages"] = [
            HumanMessage(content="Find me some undervalued players I could trade for")
        ]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        result_messages = cast(dict[str, Any], update).get("messages", [])
        tool_calls = extract_tool_calls_from_messages(result_messages)
        tool_names = [tc["name"] for tc in tool_calls]

        assert "trade" in tool_names, (
            f"Expected 'trade' in tool calls, got: {tool_names}"
        )
