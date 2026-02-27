"""Eval for users with no Yahoo Fantasy leagues."""

import uuid

import pytest
from langchain_core.messages import HumanMessage

from agent.agent_state import AgentState
from agent.SupervisorAgent import supervisor_node
from tests.evals.conftest import retry_on_rate_limit

NO_TEAMS_KEYWORDS = (
    "no team",
    "no league",
    "don't have",
    "doesn't have",
    "no fantasy",
    "not found",
    "no hockey",
    "haven't joined",
    "no active",
)
JOIN_KEYWORDS = ("join", "create", "sign up", "start", "set up")


class TestNoYahooLeagues:

    @pytest.fixture
    def authenticated_no_leagues_state(self) -> AgentState:
        return AgentState(
            messages=[],
            user_email="noleagues@example.com",
            league_id=None,
            team_id=None,
            thread_id=str(uuid.uuid4()),
            user_teams=[],
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_user_with_no_leagues_gets_guidance(
        self,
        authenticated_no_leagues_state,
        mocker,
    ):
        mocker.patch(
            "data.yahoo_user_team_repository.YahooUserTeamRepository.get_user_teams_with_league_info",
            return_value=[],
        )

        mocker.patch(
            "data.yahoo_token_repository.load_tokens_from_db",
            return_value={"access_token": "test_token", "refresh_token": "test_refresh"},
        )

        mock_client = mocker.MagicMock()
        from yfpy.exceptions import YahooFantasySportsDataNotFound

        mock_client.query.get_user_teams.side_effect = YahooFantasySportsDataNotFound(
            "No data found when attempting extraction from fields: ['users', '0', 'user', 'games']"
        )
        mocker.patch(
            "tools.yahoo.get_user_leagues.AuthenticatedYahooClient",
            return_value=mock_client,
        )

        mock_memory_store = mocker.MagicMock()
        mock_memory_store.search.return_value = [{"content": "past conversation"}]
        mocker.patch("agent.memory_store.get_memory_store", return_value=mock_memory_store)

        authenticated_no_leagues_state["messages"] = [
            HumanMessage(content="Hey Gordie, help me with my fantasy team!")
        ]
        result = supervisor_node(authenticated_no_leagues_state)

        update = result.update or {}
        response_text = update.get("response", "")
        response_lower = response_text.lower()

        assert response_text, "Agent produced no response"
        assert "error" not in response_lower or "encountered" not in response_lower, (
            f"Agent returned error response: {response_text[:500]}"
        )

        assert any(kw in response_lower for kw in NO_TEAMS_KEYWORDS), (
            f"Expected no-teams language in response: {response_text[:500]}"
        )
        assert any(kw in response_lower for kw in JOIN_KEYWORDS), (
            f"Expected join/create keyword in response: {response_text[:500]}"
        )
