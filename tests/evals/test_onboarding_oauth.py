import uuid

import pytest
from langchain_core.messages import HumanMessage

from agent.agent_state import AgentState
from agent.context_node import context_node
from agent.SupervisorAgent import supervisor_node
from tests.evals.conftest import retry_on_rate_limit

CONNECT_KEYWORDS = ("connect", "link", "authorize", "sign in", "log in", "login")


def _run_through_context_and_supervisor(state: AgentState):
    context_result = context_node(state)
    for key, value in context_result.items():
        state[key] = value
    return supervisor_node(state)


class TestOnboardingOAuth:

    @pytest.fixture
    def unauthenticated_user_state(self) -> AgentState:
        return AgentState(
            messages=[],
            user_email="newuser@example.com",
            league_id=None,
            team_id=None,
            thread_id=str(uuid.uuid4()),
            user_teams=[],
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_first_email_includes_oauth_link(
        self,
        unauthenticated_user_state,
        mocker,
    ):
        mocker.patch(
            "data.yahoo_user_team_repository.YahooUserTeamRepository.get_user_teams_with_league_info",
            return_value=[],
        )

        mock_memory_store = mocker.MagicMock()
        mock_memory_store.search.return_value = []
        mocker.patch("agent.memory_store.get_memory_store", return_value=mock_memory_store)

        mock_oauth_url = "https://api.login.yahoo.com/oauth2/request_auth?client_id=test123"
        mock_oauth_tool = mocker.MagicMock()
        mock_oauth_tool.invoke.return_value = mock_oauth_url
        mocker.patch(
            "agent.context_node.generate_oauth_link",
            mock_oauth_tool,
        )

        unauthenticated_user_state["messages"] = [
            HumanMessage(content="Hey, I want to get help with my fantasy hockey team!")
        ]
        result = _run_through_context_and_supervisor(unauthenticated_user_state)

        update = result.update or {}
        response_text = update.get("response", "")

        assert response_text, "Agent produced no response"
        assert "error" not in response_text.lower() or "encountered" not in response_text.lower(), (
            f"Agent returned error response: {response_text[:500]}"
        )

        assert "yahoo" in response_text.lower() or "login.yahoo.com" in response_text, (
            f"Expected OAuth URL in response: {response_text[:500]}"
        )
        assert any(kw in response_text.lower() for kw in CONNECT_KEYWORDS), (
            f"Expected connect/link/authorize keyword: {response_text[:500]}"
        )
