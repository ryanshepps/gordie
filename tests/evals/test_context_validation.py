"""Evals for context validation and onboarding flow.

Tests the context_validator.py logic to ensure:
1. First-time users get welcome message + OAuth link
2. Returning users without teams get OAuth link
3. Users with multiple teams get clarification request
4. Users with one team proceed normally
"""

import uuid
from typing import Any, cast

import pytest
from agentevals.trajectory.llm import create_trajectory_llm_as_judge
from langchain_core.messages import HumanMessage

from agent.agent_state import AgentState
from agent.SupervisorAgent import supervisor_node
from tests.evals.conftest import retry_on_rate_limit


class TestFirstTimeUser:
    """Test first-time user detection and welcome flow."""

    @pytest.fixture
    def first_time_user_state(self) -> AgentState:
        """User state for a first-time user with no teams."""
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
        """Verify first-time user receives welcome message with OAuth link."""
        # Mock get_user_teams_with_league_info to return empty list
        mocker.patch(
            "data.yahoo_user_team_repository.YahooUserTeamRepository.get_user_teams_with_league_info",
            return_value=[],
        )

        # Mock memory store to return no past conversations (first-time user)
        mock_memory_store = mocker.MagicMock()
        mock_memory_store.search.return_value = []  # No past conversations
        mocker.patch("agent.memory_store.get_memory_store", return_value=mock_memory_store)

        # Mock OAuth link generation
        mock_oauth_url = "https://api.login.yahoo.com/oauth2/request_auth?client_id=test123"
        mock_oauth_tool = mocker.MagicMock()
        mock_oauth_tool.invoke.return_value = mock_oauth_url
        mocker.patch(
            "agent.context_validator.generate_oauth_link",
            mock_oauth_tool,
        )

        evaluator = create_trajectory_llm_as_judge(
            prompt="""Evaluate if this response properly welcomes a first-time user.

            The agent should:
            1. Introduce themselves (as Gordie)
            2. Explain their capabilities (roster advice, trade analysis, player comparisons, etc.)
            3. Include an OAuth/authorization link
            4. Be welcoming and friendly

            <trajectory>
            {outputs}
            </trajectory>

            Criteria:
            1. Contains introduction/welcome
            2. Explains capabilities
            3. Contains OAuth URL
            4. Friendly tone

            Score 1.0 if all criteria met, 0.0 if missing key elements.
            """,
            continuous=True,
            model="openai:gpt-4o-mini",
        )

        first_time_user_state["messages"] = [
            HumanMessage(content="Hi, can you help me with fantasy hockey?")
        ]
        result = supervisor_node(first_time_user_state)

        update = result.update or {}
        response_text = cast(dict[str, Any], update).get("response", "")

        eval_result = evaluator(
            outputs=[{"role": "assistant", "content": response_text}],
            reference_outputs=[],
        )

        eval_dict = cast(dict[str, Any], cast(object, eval_result))
        assert eval_dict["score"] == 1.0, (
            f"First-time user welcome inadequate: {eval_dict.get('comment')}\n"
            f"Response: {response_text}"
        )


class TestReturningUserNoTeams:
    """Test returning user (has messaged before) but no teams connected."""

    @pytest.fixture
    def returning_user_no_teams_state(self) -> AgentState:
        """Returning user with conversation history but no teams."""
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
        """Verify returning user without teams is prompted to connect."""
        # Mock get_user_teams_with_league_info to return empty list
        mocker.patch(
            "data.yahoo_user_team_repository.YahooUserTeamRepository.get_user_teams_with_league_info",
            return_value=[],
        )

        # Mock memory store to return past conversations (NOT first-time user)
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

        # Mock OAuth link generation
        mock_oauth_url = "https://api.login.yahoo.com/oauth2/request_auth?client_id=test123"
        mock_oauth_tool = mocker.MagicMock()
        mock_oauth_tool.invoke.return_value = mock_oauth_url
        mocker.patch(
            "agent.context_validator.generate_oauth_link",
            mock_oauth_tool,
        )

        evaluator = create_trajectory_llm_as_judge(
            prompt="""Evaluate if this response properly handles a returning user with no teams.

            The agent should:
            1. Indicate that they need to connect their Yahoo Fantasy team
            2. Include an OAuth/authorization link
            3. NOT proceed with their request until they onboard

            <trajectory>
            {outputs}
            </trajectory>

            Criteria:
            1. Mentions need to connect/link Yahoo account
            2. Contains OAuth URL
            3. Doesn't attempt to answer fantasy-specific request

            Score 1.0 if all criteria met, 0.0 if tries to answer request without team.
            """,
            continuous=True,
            model="openai:gpt-4o-mini",
        )

        returning_user_no_teams_state["messages"] = [
            HumanMessage(content="Who should I start this week?")
        ]
        result = supervisor_node(returning_user_no_teams_state)

        update = result.update or {}
        response_text = cast(dict[str, Any], update).get("response", "")

        eval_result = evaluator(
            outputs=[{"role": "assistant", "content": response_text}],
            reference_outputs=[],
        )

        eval_dict = cast(dict[str, Any], cast(object, eval_result))
        assert eval_dict["score"] == 1.0, (
            f"Returning user without teams not handled properly: {eval_dict.get('comment')}\n"
            f"Response: {response_text}"
        )


class TestMultipleTeamsClarification:
    """Test team clarification when user has multiple teams."""

    @pytest.fixture
    def multi_team_user_state(self) -> AgentState:
        """User with multiple teams connected."""
        return AgentState(
            messages=[],
            user_email="multiuser@example.com",
            league_id=None,  # Not specified
            team_id=None,  # Not specified
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
        """Verify user with multiple teams is asked to clarify which team."""
        # Mock OAuth tokens (user is authenticated)
        mocker.patch(
            "data.yahoo_token_repository.load_tokens_from_db",
            return_value={"access_token": "mock_token", "refresh_token": "mock_refresh"},
        )

        # Mock get_user_teams_with_league_info to return multiple teams
        mocker.patch(
            "data.yahoo_user_team_repository.YahooUserTeamRepository.get_user_teams_with_league_info",
            return_value=multi_team_user_state.get("user_teams", []),
        )

        # Mock memory store (has conversations, not first-time)
        mock_memory_store = mocker.MagicMock()
        mock_memory_store.search.return_value = [{"value": {"summary": "Past convo"}}]
        mocker.patch("agent.memory_store.get_memory_store", return_value=mock_memory_store)

        evaluator = create_trajectory_llm_as_judge(
            prompt="""Evaluate if this response properly requests team clarification.

            The user has multiple teams and the agent cannot determine which one they're asking about.

            The agent should:
            1. Indicate that they have multiple teams
            2. List the teams (Team Alpha and Team Beta)
            3. Ask which team the user is referring to
            4. NOT proceed with the request

            <trajectory>
            {outputs}
            </trajectory>

            Criteria:
            1. Mentions multiple teams
            2. Lists the team names or league names
            3. Asks for clarification

            Score 1.0 if all criteria met, 0.0 if proceeds without clarification.
            """,
            continuous=True,
            model="openai:gpt-4o-mini",
        )

        multi_team_user_state["messages"] = [HumanMessage(content="Should I trade my center?")]
        result = supervisor_node(multi_team_user_state)

        update = result.update or {}
        response_text = cast(dict[str, Any], update).get("response", "")

        eval_result = evaluator(
            outputs=[{"role": "assistant", "content": response_text}],
            reference_outputs=[],
        )

        eval_dict = cast(dict[str, Any], cast(object, eval_result))
        assert eval_dict["score"] >= 1.0, (
            f"Multi-team clarification inadequate: {eval_dict.get('comment')}\n"
            f"Response: {response_text}"
        )


class TestSingleTeamProceeds:
    """Test that user with one team proceeds normally."""

    @pytest.fixture
    def single_team_user_state(self, mock_yahoo_tools) -> AgentState:
        """User with one team connected."""
        return AgentState(
            messages=[],
            user_email="singleuser@example.com",
            league_id=None,  # Will be auto-assigned
            team_id=None,  # Will be auto-assigned
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
        """Verify user with one team has it auto-assigned and request proceeds."""
        # Mock OAuth tokens (user is authenticated)
        mocker.patch(
            "data.yahoo_token_repository.load_tokens_from_db",
            return_value={"access_token": "mock_token", "refresh_token": "mock_refresh"},
        )

        # Mock get_user_teams_with_league_info to return one team
        mocker.patch(
            "data.yahoo_user_team_repository.YahooUserTeamRepository.get_user_teams_with_league_info",
            return_value=single_team_user_state.get("user_teams", []),
        )

        # Mock memory store (has conversations, not first-time)
        mock_memory_store = mocker.MagicMock()
        mock_memory_store.search.return_value = [{"value": {"summary": "Past convo"}}]
        mocker.patch("agent.memory_store.get_memory_store", return_value=mock_memory_store)

        # Mock get_roster tool's underlying call to return valid roster data
        # The tool internally calls yahoo_query.get_team_roster_player_stats
        # We need to ensure this returns data that works well when converted to string
        mock_roster_result = [
            "Leon Draisaitl (C - EDM): 45 points",
            "Connor McDavid (C - EDM): 52 points",
            "Timo Meier (LW - NJD): 28 points",
        ]
        # Override the mock_yahoo_tools fixture's roster response for this test
        mock_yahoo_tools[
            "yahoo_client"
        ].query.get_team_roster_player_stats.return_value = mock_roster_result

        evaluator = create_trajectory_llm_as_judge(
            prompt="""Evaluate if this response properly handles a user with one team.

            The user has only one team, so the agent should:
            1. Automatically use that team context
            2. Proceed with their request
            3. NOT ask for team clarification
            4. NOT ask them to onboard

            <trajectory>
            {outputs}
            </trajectory>

            Criteria:
            1. Response attempts to answer the question
            2. Does NOT ask which team
            3. Does NOT ask to onboard/connect account

            Score 1.0 if proceeds normally, 0.0 if asks for clarification unnecessarily.
            """,
            continuous=True,
            model="openai:gpt-4o-mini",
        )

        single_team_user_state["messages"] = [HumanMessage(content="Show me my roster")]
        result = supervisor_node(single_team_user_state)

        update = result.update or {}
        response_text = cast(dict[str, Any], update).get("response", "")

        eval_result = evaluator(
            outputs=[{"role": "assistant", "content": response_text}],
            reference_outputs=[],
        )

        eval_dict = cast(dict[str, Any], cast(object, eval_result))
        assert eval_dict["score"] >= 1.0, (
            f"Single team handling inadequate: {eval_dict.get('comment')}\n"
            f"Response: {response_text}"
        )


class TestOAuthURLPresence:
    """Test that OAuth URLs are never omitted when needed."""

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_oauth_url_never_paraphrased(self, mocker):
        """Verify OAuth URLs are included exactly, not paraphrased."""
        # Mock get_user_teams_with_league_info to return empty list
        mocker.patch(
            "data.yahoo_user_team_repository.YahooUserTeamRepository.get_user_teams_with_league_info",
            return_value=[],
        )

        # Mock memory store (first-time user)
        mock_memory_store = mocker.MagicMock()
        mock_memory_store.search.return_value = []
        mocker.patch("agent.memory_store.get_memory_store", return_value=mock_memory_store)

        # Mock OAuth link with specific URL we can verify
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
        response_text = cast(dict[str, Any], update).get("response", "")

        # Check that the actual URL is in the response (not paraphrased)
        assert "https://api.login.yahoo.com" in response_text, (
            f"OAuth URL not found in response. "
            f"Expected URL containing 'https://api.login.yahoo.com' "
            f"but got: {response_text}"
        )
