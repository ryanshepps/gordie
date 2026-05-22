"""Routing evals for the statistician sub-agent.

These tests verify that the supervisor LLM correctly routes statistical
analysis questions to the statistician tool. They invoke the real LLM,
so they are non-deterministic and should be treated as evals, not unit tests.
"""

from typing import Any, cast

import pytest
from langchain_core.messages import HumanMessage

from agent.agent_state import AgentState
from agent.SupervisorAgent import supervisor_node
from tests.evals.conftest import extract_tool_calls_from_messages, retry_on_rate_limit


@pytest.mark.integration
class TestStatisticianRouting:
    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_consistency_question_routes_to_statistician(
        self,
        mock_user_state: AgentState,
        mock_yahoo_tools: dict[str, Any],
    ) -> None:
        mock_user_state["messages"] = [
            HumanMessage(content="Which team has the most consistent weekly scoring?")
        ]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        result_messages = cast(dict[str, Any], update).get("messages", [])
        tool_calls = extract_tool_calls_from_messages(result_messages)
        tool_names = [tc["name"] for tc in tool_calls]

        assert "statistician" in tool_names, (
            f"Expected 'statistician' in tool calls, got: {tool_names}"
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_luck_question_routes_to_statistician(
        self,
        mock_user_state: AgentState,
        mock_yahoo_tools: dict[str, Any],
    ) -> None:
        mock_user_state["messages"] = [HumanMessage(content="Am I lucky or just good this season?")]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        result_messages = cast(dict[str, Any], update).get("messages", [])
        tool_calls = extract_tool_calls_from_messages(result_messages)
        tool_names = [tc["name"] for tc in tool_calls]

        assert "statistician" in tool_names, (
            f"Expected 'statistician' in tool calls, got: {tool_names}"
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_zscore_question_routes_to_statistician(
        self,
        mock_user_state: AgentState,
        mock_yahoo_tools: dict[str, Any],
    ) -> None:
        mock_user_state["messages"] = [
            HumanMessage(content="What are the z-scores for my starters?")
        ]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        result_messages = cast(dict[str, Any], update).get("messages", [])
        tool_calls = extract_tool_calls_from_messages(result_messages)
        tool_names = [tc["name"] for tc in tool_calls]

        assert "statistician" in tool_names, (
            f"Expected 'statistician' in tool calls, got: {tool_names}"
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_trade_question_does_not_route_to_statistician(
        self,
        mock_user_state: AgentState,
        mock_yahoo_tools: dict[str, Any],
    ) -> None:
        mock_user_state["messages"] = [HumanMessage(content="Who should I trade Draisaitl for?")]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        result_messages = cast(dict[str, Any], update).get("messages", [])
        tool_calls = extract_tool_calls_from_messages(result_messages)
        tool_names = [tc["name"] for tc in tool_calls]

        assert "trade" in tool_names, (
            f"Expected 'trade' in tool calls (not statistician), got: {tool_names}"
        )
