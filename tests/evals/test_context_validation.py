import uuid
from typing import ClassVar

import pytest
from langchain_core.messages import HumanMessage

from agent.agent_state import AgentState
from agent.context_node import context_node
from agent.SupervisorAgent import supervisor_node
from data.models import Medium
from tests.evals.conftest import retry_on_rate_limit

CONNECT_KEYWORDS = ("connect", "link", "authorize", "sign in", "log in", "login")
ONBOARDING_KEYWORDS = ("connect", "link", "authorize", "onboard", "sign in", "log in")
CAPABILITY_KEYWORDS = ("roster", "trade", "player", "advice", "fantasy", "lineup", "matchup")

FIRST_TIME_USER_ID = "00000000-0000-0000-0000-000000000101"
RETURNING_USER_ID = "00000000-0000-0000-0000-000000000102"
MULTI_USER_ID = "00000000-0000-0000-0000-000000000103"
SINGLE_USER_ID = "00000000-0000-0000-0000-000000000104"
NO_TEAMS_USER_ID = "00000000-0000-0000-0000-000000000105"
SELECT_TEAM_USER_ID = "00000000-0000-0000-0000-000000000106"
AUTO_ONBOARD_USER_ID = "00000000-0000-0000-0000-000000000107"
ERROR_USER_ID = "00000000-0000-0000-0000-000000000108"
URL_TEST_USER_ID = "00000000-0000-0000-0000-000000000109"


def _run_through_context_and_supervisor(state: AgentState):
    context_result = context_node(state)
    for key, value in context_result.items():
        state[key] = value
    return supervisor_node(state)


class TestFirstTimeUser:
    @pytest.fixture
    def first_time_user_state(self) -> AgentState:
        return AgentState(
            messages=[],
            user_id=FIRST_TIME_USER_ID,
            external_id="firsttime@example.com",
            channel=Medium.EMAIL,
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
            "data.yahoo_token_repository.load_tokens_from_db_by_user_id", return_value=None
        )
        mocker.patch(
            "data.yahoo_user_team_repository.YahooUserTeamRepository.get_user_teams_with_league_info_by_user_id",
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

        first_time_user_state["messages"] = [
            HumanMessage(content="Hi, can you help me with fantasy hockey?")
        ]
        result = _run_through_context_and_supervisor(first_time_user_state)

        update = result.update or {}
        response_text = update.get("response", "")
        response_lower = response_text.lower()

        assert "gordie" in response_lower, (
            f"Expected agent to introduce itself as Gordie: {response_text[:500]}"
        )
        assert (
            "yahoo" in response_lower
            or "oauth" in response_lower
            or "login.yahoo.com" in response_text
        ), f"Expected OAuth URL in response: {response_text[:500]}"
        assert any(kw in response_lower for kw in CAPABILITY_KEYWORDS), (
            f"Expected mention of capabilities: {response_text[:500]}"
        )


class TestReturningUserNoTeams:
    @pytest.fixture
    def returning_user_no_teams_state(self) -> AgentState:
        return AgentState(
            messages=[],
            user_id=RETURNING_USER_ID,
            external_id="returning@example.com",
            channel=Medium.EMAIL,
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
            "data.yahoo_token_repository.load_tokens_from_db_by_user_id", return_value=None
        )
        mocker.patch(
            "data.yahoo_user_team_repository.YahooUserTeamRepository.get_user_teams_with_league_info_by_user_id",
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
            "agent.context_node.generate_oauth_link",
            mock_oauth_tool,
        )

        returning_user_no_teams_state["messages"] = [
            HumanMessage(content="Who should I start this week?")
        ]
        result = _run_through_context_and_supervisor(returning_user_no_teams_state)

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
            user_id=MULTI_USER_ID,
            external_id="multiuser@example.com",
            channel=Medium.EMAIL,
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
            "data.yahoo_token_repository.load_tokens_from_db_by_user_id",
            return_value={"access_token": "mock_token", "refresh_token": "mock_refresh"},
        )

        mocker.patch(
            "data.yahoo_user_team_repository.YahooUserTeamRepository.get_user_teams_with_league_info_by_user_id",
            return_value=multi_team_user_state.get("user_teams", []),
        )

        mock_memory_store = mocker.MagicMock()
        mock_memory_store.search.return_value = [{"value": {"summary": "Past convo"}}]
        mocker.patch("agent.memory_store.get_memory_store", return_value=mock_memory_store)

        multi_team_user_state["messages"] = [HumanMessage(content="Should I trade my center?")]
        result = _run_through_context_and_supervisor(multi_team_user_state)

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
            user_id=SINGLE_USER_ID,
            external_id="singleuser@example.com",
            channel=Medium.EMAIL,
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
            "data.yahoo_token_repository.load_tokens_from_db_by_user_id",
            return_value={"access_token": "mock_token", "refresh_token": "mock_refresh"},
        )

        mocker.patch(
            "data.yahoo_user_team_repository.YahooUserTeamRepository.get_user_teams_with_league_info_by_user_id",
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
        result = _run_through_context_and_supervisor(single_team_user_state)

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


class TestNoTeamsAvailable:
    @pytest.fixture
    def no_teams_state(self) -> AgentState:
        return AgentState(
            messages=[],
            user_id=NO_TEAMS_USER_ID,
            external_id="noteams@example.com",
            channel=Medium.EMAIL,
            league_id=None,
            team_id=None,
            thread_id=str(uuid.uuid4()),
            user_teams=[],
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_no_supported_teams_tells_user_to_create_one(
        self,
        no_teams_state: AgentState,
        mocker,
    ):
        mocker.patch(
            "data.yahoo_token_repository.load_tokens_from_db_by_user_id",
            return_value={"access_token": "mock_token", "refresh_token": "mock_refresh"},
        )
        mocker.patch(
            "data.yahoo_user_team_repository.YahooUserTeamRepository.get_user_teams_with_league_info_by_user_id",
            return_value=[],
        )
        mocker.patch(
            "agent.context_node.fetch_supported_teams",
            return_value=[],
        )

        mock_memory_store = mocker.MagicMock()
        mock_memory_store.search.return_value = [{"value": {"summary": "Past convo"}}]
        mocker.patch("agent.memory_store.get_memory_store", return_value=mock_memory_store)

        no_teams_state["messages"] = [HumanMessage(content="Can you help me with my lineup?")]
        result = _run_through_context_and_supervisor(no_teams_state)

        update = result.update or {}
        response_text = update.get("response", "")
        response_lower = response_text.lower()

        assert "yahoo" in response_lower or "fantasy" in response_lower, (
            f"Expected mention of Yahoo Fantasy: {response_text[:500]}"
        )
        create_keywords = ("create", "join", "set up", "sign up", "make")
        assert any(kw in response_lower for kw in create_keywords), (
            f"Expected instruction to create/join a team: {response_text[:500]}"
        )


class TestTeamSelectionNeeded:
    YAHOO_TEAMS: ClassVar[list[dict[str, str | bool]]] = [
        {
            "sport": "nhl",
            "season": "2025",
            "game_key": "465",
            "league_id": "11111",
            "team_id": "3",
            "team_name": "Ice Breakers",
            "is_active": True,
        },
        {
            "sport": "nhl",
            "season": "2025",
            "game_key": "465",
            "league_id": "22222",
            "team_id": "7",
            "team_name": "Puck Stops Here",
            "is_active": True,
        },
    ]

    @pytest.fixture
    def team_selection_state(self) -> AgentState:
        return AgentState(
            messages=[],
            user_id=SELECT_TEAM_USER_ID,
            external_id="selectteam@example.com",
            channel=Medium.EMAIL,
            league_id=None,
            team_id=None,
            thread_id=str(uuid.uuid4()),
            user_teams=[],
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_multiple_yahoo_teams_asks_which_to_onboard(
        self,
        team_selection_state: AgentState,
        mocker,
    ):
        mocker.patch(
            "data.yahoo_token_repository.load_tokens_from_db_by_user_id",
            return_value={"access_token": "mock_token", "refresh_token": "mock_refresh"},
        )
        mocker.patch(
            "data.yahoo_user_team_repository.YahooUserTeamRepository.get_user_teams_with_league_info_by_user_id",
            return_value=[],
        )
        mocker.patch(
            "agent.context_node.fetch_supported_teams",
            return_value=self.YAHOO_TEAMS,
        )

        mock_memory_store = mocker.MagicMock()
        mock_memory_store.search.return_value = [{"value": {"summary": "Past convo"}}]
        mocker.patch("agent.memory_store.get_memory_store", return_value=mock_memory_store)

        team_selection_state["messages"] = [HumanMessage(content="Help me with my fantasy team")]
        result = _run_through_context_and_supervisor(team_selection_state)

        update = result.update or {}
        response_text = update.get("response", "")
        response_lower = response_text.lower()

        assert "ice breakers" in response_lower or "puck stops" in response_lower, (
            f"Expected team names mentioned: {response_text[:500]}"
        )
        question_words = ("which", "what", "?")
        assert any(w in response_lower for w in question_words), (
            f"Expected question asking which team: {response_text[:500]}"
        )


class TestAutoOnboarded:
    SINGLE_ACTIVE_TEAM: ClassVar[dict[str, str | bool]] = {
        "sport": "nhl",
        "season": "2025",
        "game_key": "465",
        "league_id": "33333",
        "team_id": "5",
        "team_name": "Gordie's Grinders",
        "is_active": True,
    }

    @pytest.fixture
    def auto_onboard_state(self) -> AgentState:
        return AgentState(
            messages=[],
            user_id=AUTO_ONBOARD_USER_ID,
            external_id="autoonboard@example.com",
            channel=Medium.EMAIL,
            league_id=None,
            team_id=None,
            thread_id=str(uuid.uuid4()),
            user_teams=[],
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_single_active_team_confirms_onboarding(
        self,
        auto_onboard_state: AgentState,
        mocker,
    ):
        mocker.patch(
            "data.yahoo_token_repository.load_tokens_from_db_by_user_id",
            return_value={"access_token": "mock_token", "refresh_token": "mock_refresh"},
        )
        mocker.patch(
            "data.yahoo_user_team_repository.YahooUserTeamRepository.get_user_teams_with_league_info_by_user_id",
            return_value=[],
        )
        mocker.patch(
            "agent.context_node.fetch_supported_teams",
            return_value=[self.SINGLE_ACTIVE_TEAM],
        )
        mocker.patch(
            "agent.context_node.auto_onboard_team",
            return_value=self.SINGLE_ACTIVE_TEAM,
        )

        mock_memory_store = mocker.MagicMock()
        mock_memory_store.search.return_value = [{"value": {"summary": "Past convo"}}]
        mocker.patch("agent.memory_store.get_memory_store", return_value=mock_memory_store)

        auto_onboard_state["messages"] = [
            HumanMessage(content="Hey, I need help with my fantasy team")
        ]
        result = _run_through_context_and_supervisor(auto_onboard_state)

        update = result.update or {}
        response_text = update.get("response", "")
        response_lower = response_text.lower()

        connected_keywords = ("connected", "set up", "onboarded", "ready", "linked")
        assert any(kw in response_lower for kw in connected_keywords), (
            f"Expected confirmation that team was connected: {response_text[:500]}"
        )
        help_keywords = ("trade", "waiver", "lineup", "roster", "help", "advice", "assist")
        assert any(kw in response_lower for kw in help_keywords), (
            f"Expected offer to help: {response_text[:500]}"
        )


class TestContextError:
    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_api_failure_returns_error_response(self, mocker):
        mocker.patch(
            "data.yahoo_token_repository.load_tokens_from_db_by_user_id",
            return_value={"access_token": "mock_token", "refresh_token": "mock_refresh"},
        )
        mocker.patch(
            "data.yahoo_user_team_repository.YahooUserTeamRepository.get_user_teams_with_league_info_by_user_id",
            return_value=[],
        )
        mocker.patch(
            "agent.context_node.fetch_supported_teams",
            side_effect=RuntimeError("Yahoo API timeout"),
        )

        mock_memory_store = mocker.MagicMock()
        mock_memory_store.search.return_value = [{"value": {"summary": "Past convo"}}]
        mocker.patch("agent.memory_store.get_memory_store", return_value=mock_memory_store)

        state = AgentState(
            messages=[HumanMessage(content="Help me with my roster")],
            user_id=ERROR_USER_ID,
            external_id="erroruser@example.com",
            channel=Medium.EMAIL,
            league_id=None,
            team_id=None,
            thread_id=str(uuid.uuid4()),
            user_teams=[],
        )

        result = _run_through_context_and_supervisor(state)
        update = result.update or {}
        response_text = update.get("response", "")
        response_lower = response_text.lower()

        apologize_keywords = ("sorry", "apologize", "issue", "error", "problem")
        assert any(kw in response_lower for kw in apologize_keywords), (
            f"Expected apology or error acknowledgment: {response_text[:500]}"
        )
        retry_keywords = ("try again", "retry", "moment", "later")
        assert any(kw in response_lower for kw in retry_keywords), (
            f"Expected suggestion to try again: {response_text[:500]}"
        )


class TestOAuthURLPresence:
    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_oauth_url_never_paraphrased(self, mocker):
        mocker.patch(
            "data.yahoo_token_repository.load_tokens_from_db_by_user_id", return_value=None
        )
        mocker.patch(
            "data.yahoo_user_team_repository.YahooUserTeamRepository.get_user_teams_with_league_info_by_user_id",
            return_value=[],
        )

        mock_memory_store = mocker.MagicMock()
        mock_memory_store.search.return_value = []
        mocker.patch("agent.memory_store.get_memory_store", return_value=mock_memory_store)

        mock_oauth_url = "https://api.login.yahoo.com/oauth2/request_auth?client_id=dj0test&redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fcallback"
        mock_oauth_tool = mocker.MagicMock()
        mock_oauth_tool.invoke.return_value = mock_oauth_url
        mocker.patch(
            "agent.context_node.generate_oauth_link",
            mock_oauth_tool,
        )

        state = AgentState(
            messages=[HumanMessage(content="Help me with fantasy hockey")],
            user_id=URL_TEST_USER_ID,
            external_id="urltest@example.com",
            channel=Medium.EMAIL,
            league_id=None,
            team_id=None,
            thread_id=str(uuid.uuid4()),
            user_teams=[],
        )

        result = _run_through_context_and_supervisor(state)
        update = result.update or {}
        response_text = update.get("response", "")

        assert "https://api.login.yahoo.com" in response_text, (
            f"OAuth URL not found in response. "
            f"Expected URL containing 'https://api.login.yahoo.com' "
            f"but got: {response_text}"
        )
