"""Evals for context validation and onboarding flow.

Tests the context_validator.py logic to ensure:
1. First-time users get welcome message + OAuth link
2. Returning users without teams get OAuth link
3. Users with multiple teams get clarification request
4. Users with one team proceed normally
"""

import uuid

import pytest
from langchain_core.messages import HumanMessage

from agent.agent_state import AgentState
from agent.SupervisorAgent import supervisor_node
from tests.evals.conftest import retry_on_rate_limit

CONNECT_KEYWORDS = ("connect", "link", "authorize", "sign in", "log in", "login")
ONBOARDING_KEYWORDS = ("connect", "link", "authorize", "onboard", "sign in", "log in")
CAPABILITY_KEYWORDS = ("roster", "trade", "player", "advice", "fantasy", "lineup", "matchup")


class TestFirstTimeUser:

    @pytest.fixture
    def first_time_user_state(self) -> AgentState:
        return AgentState(
            messages=[],
            user_email="firsttime@example.com",
            league_id=None,
            team_id=None,
            thread_id=str(uuid.uuid4()),
            user_teams=[],
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_first_time_user_gets_welcome_and_oauth(
        self,
        first_time_user_state: AgentState,
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
            "agent.context_validator.generate_oauth_link",
            mock_oauth_tool,
        )

        first_time_user_state["messages"] = [
            HumanMessage(content="Hi, can you help me with fantasy hockey?")
        ]
        result = supervisor_node(first_time_user_state)

        update = result.update or {}
        response_text = update.get("response", "")
        response_lower = response_text.lower()

        assert "gordie" in response_lower, (
            f"Expected agent to introduce itself as Gordie: {response_text[:500]}"
        )
        assert "yahoo" in response_lower or "oauth" in response_lower or "login.yahoo.com" in response_text, (
            f"Expected OAuth URL in response: {response_text[:500]}"
        )
        assert any(kw in response_lower for kw in CAPABILITY_KEYWORDS), (
            f"Expected mention of capabilities: {response_text[:500]}"
        )


class TestReturningUserNoTeams:

    @pytest.fixture
    def returning_user_no_teams_state(self) -> AgentState:
        return AgentState(
            messages=[],
            user_email="returning@example.com",
            league_id=None,
            team_id=None,
            thread_id=str(uuid.uuid4()),
            user_teams=[],
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_returning_user_no_teams_gets_onboarding_prompt(
        self,
        returning_user_no_teams_state: AgentState,
        mocker,
    ):
        mocker.patch(
            "data.yahoo_user_team_repository.YahooUserTeamRepository.get_user_teams_with_league_info",
            return_value=[],
        )

        mock_memory_store = mocker.MagicMock()
        mock_memory_store.search.return_value = [
            {
                "value": {
                    "summary": "Previous conversation",
                    "created_at": "2024-01-01",
                }
            }
        ]
        mocker.patch("agent.memory_store.get_memory_store", return_value=mock_memory_store)

        mock_oauth_url = "https://api.login.yahoo.com/oauth2/request_auth?client_id=test123"
        mock_oauth_tool = mocker.MagicMock()
        mock_oauth_tool.invoke.return_value = mock_oauth_url
        mocker.patch(
            "agent.context_validator.generate_oauth_link",
            mock_oauth_tool,
        )

        returning_user_no_teams_state["messages"] = [
            HumanMessage(content="Who should I start this week?")
        ]
        result = supervisor_node(returning_user_no_teams_state)

        update = result.update or {}
        response_text = update.get("response", "")
        response_lower = response_text.lower()

        assert "yahoo" in response_lower or "login.yahoo.com" in response_text, (
            f"Expected OAuth URL in response: {response_text[:500]}"
        )
        assert any(kw in response_lower for kw in CONNECT_KEYWORDS), (
            f"Expected connect/link/authorize keyword: {response_text[:500]}"
        )


class TestMultipleTeamsClarification:

    @pytest.fixture
    def multi_team_user_state(self) -> AgentState:
        return AgentState(
            messages=[],
            user_email="multiuser@example.com",
            league_id=None,
            team_id=None,
            thread_id=str(uuid.uuid4()),
            user_teams=[
                {
                    "league_id": "12345",
                    "team_id": "1",
                    "team_name": "Team Alpha",
                    "game_key": "nhl.l.12345",
                    "league_name": "League One",
                },
                {
                    "league_id": "67890",
                    "team_id": "2",
                    "team_name": "Team Beta",
                    "game_key": "nhl.l.67890",
                    "league_name": "League Two",
                },
            ],
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_multiple_teams_requests_clarification(
        self,
        multi_team_user_state: AgentState,
        mocker,
    ):
        mocker.patch(
            "data.yahoo_token_repository.load_tokens_from_db",
            return_value={"access_token": "mock_token", "refresh_token": "mock_refresh"},
        )

        mocker.patch(
            "data.yahoo_user_team_repository.YahooUserTeamRepository.get_user_teams_with_league_info",
            return_value=multi_team_user_state.get("user_teams", []),
        )

        mock_memory_store = mocker.MagicMock()
        mock_memory_store.search.return_value = [{"value": {"summary": "Past convo"}}]
        mocker.patch("agent.memory_store.get_memory_store", return_value=mock_memory_store)

        multi_team_user_state["messages"] = [HumanMessage(content="Should I trade my center?")]
        result = supervisor_node(multi_team_user_state)

        update = result.update or {}
        response_text = update.get("response", "")
        response_lower = response_text.lower()

        assert "alpha" in response_lower or "league one" in response_lower, (
            f"Expected Team Alpha or League One mentioned: {response_text[:500]}"
        )
        assert "beta" in response_lower or "league two" in response_lower, (
            f"Expected Team Beta or League Two mentioned: {response_text[:500]}"
        )
        question_words = ("which", "what", "?")
        assert any(w in response_lower for w in question_words), (
            f"Expected clarification question: {response_text[:500]}"
        )


class TestSingleTeamProceeds:

    @pytest.fixture
    def single_team_user_state(self, mock_yahoo_tools) -> AgentState:
        return AgentState(
            messages=[],
            user_email="singleuser@example.com",
            league_id=None,
            team_id=None,
            thread_id=str(uuid.uuid4()),
            user_teams=[
                {
                    "league_id": "12345",
                    "team_id": "1",
                    "team_name": "Test Team",
                    "game_key": "nhl.l.12345",
                    "league_name": "Test League",
                }
            ],
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_single_team_auto_assigned(
        self,
        single_team_user_state: AgentState,
        mocker,
        mock_yahoo_tools,
    ):
        mocker.patch(
            "data.yahoo_token_repository.load_tokens_from_db",
            return_value={"access_token": "mock_token", "refresh_token": "mock_refresh"},
        )

        mocker.patch(
            "data.yahoo_user_team_repository.YahooUserTeamRepository.get_user_teams_with_league_info",
            return_value=single_team_user_state.get("user_teams", []),
        )

        mock_memory_store = mocker.MagicMock()
        mock_memory_store.search.return_value = [{"value": {"summary": "Past convo"}}]
        mocker.patch("agent.memory_store.get_memory_store", return_value=mock_memory_store)

        mock_roster_result = [
            "Leon Draisaitl (C - EDM): 45 points",
            "Connor McDavid (C - EDM): 52 points",
            "Timo Meier (LW - NJD): 28 points",
        ]
        mock_yahoo_tools[
            "yahoo_client"
        ].query.get_team_roster_player_stats.return_value = mock_roster_result

        single_team_user_state["messages"] = [HumanMessage(content="Show me my roster")]
        result = supervisor_node(single_team_user_state)

        update = result.update or {}
        response_text = update.get("response", "")
        response_lower = response_text.lower()

        assert response_text, "Expected a non-empty response"
        assert "which team" not in response_lower, (
            f"Should not ask which team for single-team user: {response_text[:500]}"
        )
        assert not any(kw in response_lower for kw in ONBOARDING_KEYWORDS), (
            f"Should not prompt onboarding for single-team user: {response_text[:500]}"
        )


class TestOAuthURLPresence:

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_oauth_url_never_paraphrased(self, mocker):
        mocker.patch(
            "data.yahoo_user_team_repository.YahooUserTeamRepository.get_user_teams_with_league_info",
            return_value=[],
        )

        mock_memory_store = mocker.MagicMock()
        mock_memory_store.search.return_value = []
        mocker.patch("agent.memory_store.get_memory_store", return_value=mock_memory_store)

        mock_oauth_url = "https://api.login.yahoo.com/oauth2/request_auth?client_id=dj0test&redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fcallback"
        mock_oauth_tool = mocker.MagicMock()
        mock_oauth_tool.invoke.return_value = mock_oauth_url
        mocker.patch(
            "agent.context_validator.generate_oauth_link",
            mock_oauth_tool,
        )

        state = AgentState(
            messages=[HumanMessage(content="Help me with fantasy hockey")],
            user_email="urltest@example.com",
            league_id=None,
            team_id=None,
            thread_id=str(uuid.uuid4()),
            user_teams=[],
        )

        result = supervisor_node(state)
        update = result.update or {}
        response_text = update.get("response", "")

        assert "https://api.login.yahoo.com" in response_text, (
            f"OAuth URL not found in response. "
            f"Expected URL containing 'https://api.login.yahoo.com' "
            f"but got: {response_text}"
        )
