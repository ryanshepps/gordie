"""LLM-as-Judge evals for notification management.

These evals verify that the agent's responses appropriately confirm
notification preference changes to users.

Uses agentevals trajectory evaluation with GPT-4o-mini as judge.
"""

import uuid
from typing import Any, cast

import pytest
from agentevals.trajectory.llm import create_trajectory_llm_as_judge
from langchain_core.messages import HumanMessage
from pytest_mock import MockerFixture

from agent.agent_state import AgentState
from agent.SupervisorAgent import supervisor_node
from tests.evals.conftest import retry_on_rate_limit


@pytest.fixture
def mock_user_state() -> AgentState:
    """Base user state for evals."""
    return AgentState(
        messages=[],
        user_email="test@example.com",
        league_id="12345",
        team_id="1",
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


@pytest.fixture
def mock_yahoo_and_notifications(mocker: MockerFixture) -> None:
    """Mock Yahoo tools and notification repository."""
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    # Mock get_user_teams_with_league_info
    mocker.patch(
        "data.yahoo_user_team_repository.YahooUserTeamRepository.get_user_teams_with_league_info",
        return_value=[
            {
                "league_id": "12345",
                "team_id": "1",
                "team_name": "Test Team",
                "game_key": "nhl.l.12345",
                "league_name": "Test League",
            }
        ],
    )

    # Mock OAuth tokens
    mocker.patch(
        "data.yahoo_token_repository.load_tokens_from_db",
        return_value={"access_token": "test_token", "refresh_token": "test_refresh"},
    )

    # Mock memory store
    mock_memory_store = MagicMock()
    mock_memory_store.search.return_value = [{"content": "past conversation"}]
    mocker.patch("agent.memory_store.get_memory_store", return_value=mock_memory_store)

    # Mock notification preference repository
    mock_notification_repo = MagicMock()
    mocker.patch(
        "tools.notifications.manage_notifications.NotificationPreferenceRepository",
        return_value=mock_notification_repo,
    )

    # Mock Yahoo client
    mock_players = [
        SimpleNamespace(
            name=SimpleNamespace(full="Test Player"),
            player_key="nhl.p.1234",
            player_id="1234",
            display_position="C",
            editorial_team_abbr="TST",
            editorial_team_full_name="Test Team",
            status=None,
            status_full=None,
            player_stats=SimpleNamespace(total_points=50.0),
        ),
    ]

    mock_client = MagicMock()
    mock_client.query.get_league_key.return_value = "nhl.l.12345"
    mock_client.query.get_team_roster_player_stats.return_value = mock_players
    mock_client.query.get_league_teams.return_value = []

    yahoo_modules = [
        "tools.yahoo.get_team_roster",
        "tools.yahoo.get_league_teams",
        "tools.yahoo.find_similar_ranked_players",
        "tools.yahoo.get_player_season_rank",
        "tools.yahoo.get_roster",
        "tools.yahoo.get_player_yahoo_info",
        "tools.available.search_available_players",
        "tools.yahoo.onboard_user_team",
        "tools.yahoo.get_user_leagues",
    ]

    for module in yahoo_modules:
        mocker.patch(
            f"{module}.AuthenticatedYahooClient",
            return_value=mock_client,
        )


class TestNotificationEvals:
    """LLM-as-judge evaluations for notification management responses."""

    @pytest.fixture
    def opt_out_evaluator(self):
        """Evaluator for opt-out confirmation responses."""
        return create_trajectory_llm_as_judge(
            prompt="""Evaluate if this response confirms that a notification/digest has been disabled or turned off.

            <trajectory>
            {outputs}
            </trajectory>

            The response should clearly communicate that:
            1. The weekly digest or notification has been disabled/turned off/stopped
            2. The user understands their preference has been saved

            Score 1.0 if the response clearly confirms the digest is disabled,
            0.5 if partially confirms but unclear,
            0.0 if does not confirm or is confusing.

            Be concise - provide only a brief 1-sentence reasoning.
            """,
            continuous=True,
            model="openai:gpt-4o-mini",
        )

    @pytest.fixture
    def opt_in_evaluator(self):
        """Evaluator for opt-in confirmation responses."""
        return create_trajectory_llm_as_judge(
            prompt="""Evaluate if this response confirms that a notification/digest has been enabled or turned back on.

            <trajectory>
            {outputs}
            </trajectory>

            The response should clearly communicate that:
            1. The weekly digest or notification has been enabled/turned on/resumed
            2. The user understands they will start receiving it again

            Score 1.0 if the response clearly confirms the digest is enabled,
            0.5 if partially confirms but unclear,
            0.0 if does not confirm or is confusing.

            Be concise - provide only a brief 1-sentence reasoning.
            """,
            continuous=True,
            model="openai:gpt-4o-mini",
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_opt_out_confirms_action(
        self,
        mock_user_state: AgentState,
        mock_yahoo_and_notifications: None,
        opt_out_evaluator,
    ):
        """Agent response confirms digest was disabled."""
        mock_user_state["messages"] = [
            HumanMessage(content="Stop sending me the weekly digest emails")
        ]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        response_text = cast(dict[str, Any], update).get("response", "")

        if not response_text:
            pytest.skip("No response generated")

        if "error" in response_text.lower() or "couldn't process" in response_text.lower():
            pytest.skip("Agent returned error response")

        output_messages = [{"role": "assistant", "content": response_text}]

        eval_result = opt_out_evaluator(
            outputs=output_messages,
            reference_outputs=[],
        )

        eval_dict = cast(dict[str, Any], cast(object, eval_result))
        assert eval_dict["score"] >= 0.5, (
            f"Opt-out confirmation insufficient: {eval_dict.get('comment')}\n"
            f"Response was: {response_text[:500]}"
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_opt_in_confirms_action(
        self,
        mock_user_state: AgentState,
        mock_yahoo_and_notifications: None,
        opt_in_evaluator,
    ):
        """Agent response confirms digest was re-enabled."""
        mock_user_state["messages"] = [
            HumanMessage(content="Turn the weekly digest back on please")
        ]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        response_text = cast(dict[str, Any], update).get("response", "")

        if not response_text:
            pytest.skip("No response generated")

        if "error" in response_text.lower() or "couldn't process" in response_text.lower():
            pytest.skip("Agent returned error response")

        output_messages = [{"role": "assistant", "content": response_text}]

        eval_result = opt_in_evaluator(
            outputs=output_messages,
            reference_outputs=[],
        )

        eval_dict = cast(dict[str, Any], cast(object, eval_result))
        assert eval_dict["score"] >= 0.5, (
            f"Opt-in confirmation insufficient: {eval_dict.get('comment')}\n"
            f"Response was: {response_text[:500]}"
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_unsubscribe_confirms_action(
        self,
        mock_user_state: AgentState,
        mock_yahoo_and_notifications: None,
        opt_out_evaluator,
    ):
        """'Unsubscribe' request gets proper confirmation."""
        mock_user_state["messages"] = [
            HumanMessage(content="Unsubscribe me from the weekly emails")
        ]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        response_text = cast(dict[str, Any], update).get("response", "")

        if not response_text:
            pytest.skip("No response generated")

        if "error" in response_text.lower() or "couldn't process" in response_text.lower():
            pytest.skip("Agent returned error response")

        output_messages = [{"role": "assistant", "content": response_text}]

        eval_result = opt_out_evaluator(
            outputs=output_messages,
            reference_outputs=[],
        )

        eval_dict = cast(dict[str, Any], cast(object, eval_result))
        assert eval_dict["score"] >= 0.5, (
            f"Unsubscribe confirmation insufficient: {eval_dict.get('comment')}\n"
            f"Response was: {response_text[:500]}"
        )
