"""Eval for OAuth onboarding flow."""

import uuid

import pytest
from langchain_core.messages import HumanMessage

from agent.agent_state import AgentState
from agent.SupervisorAgent import supervisor_node
from tests.evals.conftest import retry_on_rate_limit

CONNECT_KEYWORDS = ("connect", "link", "authorize", "sign in", "log in", "login")


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
        mocker.patch(
            "agent.context_validator.generate_oauth_link",
            return_value=mock_oauth_url,
        )

        unauthenticated_user_state["messages"] = [
            HumanMessage(content="Hey, I want to get help with my fantasy hockey team!")
        ]
        result = supervisor_node(unauthenticated_user_state)

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
