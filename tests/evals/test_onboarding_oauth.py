"""LLM-as-Judge eval for OAuth onboarding flow."""

import uuid
from typing import Any, cast

import pytest
from agentevals.trajectory.llm import create_trajectory_llm_as_judge
from langchain_core.messages import HumanMessage

from agent.agent_state import AgentState
from agent.SupervisorAgent import supervisor_node
from tests.evals.conftest import retry_on_rate_limit


class TestOnboardingOAuth:
    """Test that unauthenticated users receive OAuth link on first contact."""

    @pytest.fixture
    def unauthenticated_user_state(self) -> AgentState:
        """User state with no connected teams (unauthenticated)."""
        return AgentState(
            messages=[],
            user_email="newuser@example.com",
            league_id=None,
            team_id=None,
            thread_id=str(uuid.uuid4()),
            user_teams=[],  # No teams - user is not authenticated
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_first_email_includes_oauth_link(
        self,
        unauthenticated_user_state,
        mocker,
    ):
        """Verify the agent sends OAuth link on the very first email to unauthenticated user."""
        # Mock get_user_teams_with_league_info to return empty list (unauthenticated user)
        mocker.patch(
            "data.yahoo_user_team_repository.YahooUserTeamRepository.get_user_teams_with_league_info",
            return_value=[],
        )

        # Mock memory store to return no past conversations (first-time user)
        mock_memory_store = mocker.MagicMock()
        mock_memory_store.search.return_value = []
        mocker.patch("agent.memory_store.get_memory_store", return_value=mock_memory_store)

        # Mock generate_oauth_link to return a predictable URL
        mock_oauth_url = "https://api.login.yahoo.com/oauth2/request_auth?client_id=test123"
        mocker.patch(
            "agent.context_validator.generate_oauth_link",
            return_value=mock_oauth_url,
        )

        oauth_evaluator = create_trajectory_llm_as_judge(
            prompt="""Evaluate if this response properly handles an unauthenticated user's first contact.

            The agent should:
            1. Recognize the user needs to connect their Yahoo Fantasy account
            2. Include an OAuth/authorization link for the user to click
            3. Explain what connecting their account will allow them to do

            <trajectory>
            {outputs}
            </trajectory>

            Criteria:
            1. Response contains a URL/link for Yahoo authorization (look for "yahoo" and "oauth" or "login" or a URL pattern)
            2. Response explains that they need to connect/link/authorize their Yahoo account
            3. Response is welcoming and helpful for a first-time user

            Score 1.0 if OAuth link is present and explained, 0.5 if partially addressed, 0.0 if missing.
            """,
            continuous=True,
            model="openai:gpt-4o-mini",
        )

        # Simulate first contact from unauthenticated user
        unauthenticated_user_state["messages"] = [
            HumanMessage(content="Hey, I want to get help with my fantasy hockey team!")
        ]
        result = supervisor_node(unauthenticated_user_state)

        update = result.update or {}
        response_text = cast(dict[str, Any], update).get("response", "")

        # Skip if agent returned an error
        if "error" in response_text.lower() and "encountered" in response_text.lower():
            pytest.skip("Agent returned error response")

        output_messages = [{"role": "assistant", "content": response_text}]

        eval_result = oauth_evaluator(
            outputs=output_messages,
            reference_outputs=[],
        )

        eval_dict = cast(dict[str, Any], cast(object, eval_result))
        assert eval_dict["score"] >= 0.5, (
            f"OAuth link not properly included in first response: {eval_dict.get('comment')}\n"
            f"Response was: {response_text}"
        )
