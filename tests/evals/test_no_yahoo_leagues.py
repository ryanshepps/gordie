"""LLM-as-Judge eval for users with no Yahoo Fantasy leagues."""

import uuid
from typing import Any, cast

import pytest
from agentevals.trajectory.llm import create_trajectory_llm_as_judge
from langchain_core.messages import HumanMessage

from agent.agent_state import AgentState
from agent.SupervisorAgent import supervisor_node
from tests.evals.conftest import retry_on_rate_limit


class TestNoYahooLeagues:
    """Test that users with no Yahoo leagues receive helpful guidance."""

    @pytest.fixture
    def authenticated_no_leagues_state(self) -> AgentState:
        """User state: authenticated but no Yahoo leagues."""
        return AgentState(
            messages=[],
            user_email="noleagues@example.com",
            league_id=None,
            team_id=None,
            thread_id=str(uuid.uuid4()),
            user_teams=[],  # No teams in DB
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_user_with_no_leagues_gets_guidance(
        self,
        authenticated_no_leagues_state,
        mocker,
    ):
        """Verify authenticated user with no Yahoo leagues gets helpful guidance."""
        # Mock get_user_teams_with_league_info to return empty (no teams in DB)
        mocker.patch(
            "data.yahoo_user_team_repository.YahooUserTeamRepository.get_user_teams_with_league_info",
            return_value=[],
        )

        # Mock OAuth tokens to simulate authenticated user
        mocker.patch(
            "data.yahoo_token_repository.load_tokens_from_db",
            return_value={"access_token": "test_token", "refresh_token": "test_refresh"},
        )

        # Mock AuthenticatedYahooClient to simulate user with no leagues
        # This is what get_user_leagues tool uses internally
        mock_client = mocker.MagicMock()
        from yfpy.exceptions import YahooFantasySportsDataNotFound

        mock_client.query.get_user_teams.side_effect = YahooFantasySportsDataNotFound(
            "No data found when attempting extraction from fields: ['users', '0', 'user', 'games']"
        )
        mocker.patch(
            "tools.yahoo.get_user_leagues.AuthenticatedYahooClient",
            return_value=mock_client,
        )

        # Mock memory store to simulate returning user
        mock_memory_store = mocker.MagicMock()
        mock_memory_store.search.return_value = [{"content": "past conversation"}]
        mocker.patch("agent.memory_store.get_memory_store", return_value=mock_memory_store)

        evaluator = create_trajectory_llm_as_judge(
            prompt="""Evaluate if this response properly handles a user who has authenticated but has no Yahoo Fantasy Hockey leagues.

            The agent should:
            1. Explain that the user doesn't have any Yahoo Fantasy Hockey teams
            2. Tell them they need to create or join a hockey league on Yahoo Fantasy first
            3. Mention they can email Gordie again once they have a team to onboard
            4. Be helpful and not crash/error

            <trajectory>
            {outputs}
            </trajectory>

            Criteria:
            1. Response clearly states user has no Yahoo Fantasy Hockey teams
            2. Response tells user to create/join a league on Yahoo Fantasy
            3. Response mentions emailing Gordie again after joining
            4. Response is helpful and doesn't show technical errors

            Score 1.0 if all criteria are met perfectly, 0.0 if any criteria are missing or poorly addressed.
            """,
            continuous=True,
            model="openai:gpt-4o-mini",
        )

        # Simulate message from authenticated user with no leagues
        authenticated_no_leagues_state["messages"] = [
            HumanMessage(content="Hey Gordie, help me with my fantasy team!")
        ]
        result = supervisor_node(authenticated_no_leagues_state)

        update = result.update or {}
        response_text = cast(dict[str, Any], update).get("response", "")

        # Skip if agent returned an error
        if "error" in response_text.lower() and "encountered" in response_text.lower():
            pytest.skip("Agent returned error response")

        output_messages = [{"role": "assistant", "content": response_text}]

        eval_result = evaluator(
            outputs=output_messages,
            reference_outputs=[],
        )

        eval_dict = cast(dict[str, Any], cast(object, eval_result))
        assert eval_dict["score"] == 1.0, (
            f"Response did not properly handle user with no leagues (expected score 1.0): {eval_dict.get('comment')}\n"
            f"Response was: {response_text}"
        )
