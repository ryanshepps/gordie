"""Evals for notification management.

Verify that the agent's responses appropriately confirm
notification preference changes to users.
"""

import pytest
from langchain_core.messages import HumanMessage
from pytest_mock import MockerFixture

from agent.agent_state import AgentState
from agent.SupervisorAgent import supervisor_node
from tests.evals.conftest import retry_on_rate_limit

OPT_OUT_KEYWORDS = (
    "disabled",
    "turned off",
    "stopped",
    "unsubscribed",
    "won't receive",
    "no longer",
    "opted out",
    "off the table",
    "won't be sending",
    "won't send",
)

OPT_IN_KEYWORDS = (
    "enabled",
    "turned on",
    "will receive",
    "reactivated",
    "resumed",
    "turned back on",
    "opted in",
    "back on",
    "signed up",
)


@pytest.fixture
def mock_yahoo_and_notifications(mocker: MockerFixture) -> None:
    from types import SimpleNamespace
    from unittest.mock import MagicMock

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

    mocker.patch(
        "data.yahoo_token_repository.load_tokens_from_db",
        return_value={"access_token": "test_token", "refresh_token": "test_refresh"},
    )

    mock_memory_store = MagicMock()
    mock_memory_store.search.return_value = [{"content": "past conversation"}]
    mocker.patch("agent.memory_store.get_memory_store", return_value=mock_memory_store)

    mock_notification_repo = MagicMock()
    mocker.patch(
        "tools.notifications.manage_notifications.NotificationPreferenceRepository",
        return_value=mock_notification_repo,
    )

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


def _extract_response(result) -> str:
    update = result.update or {}
    response_text = update.get("response", "")
    assert response_text, "Agent produced no response"
    assert (
        "error" not in response_text.lower() or "couldn't process" not in response_text.lower()
    ), f"Agent returned error response: {response_text[:500]}"
    return response_text.lower()


class TestNotificationEvals:
    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_opt_out_confirms_action(
        self,
        mock_user_state: AgentState,
        mock_yahoo_and_notifications: None,
    ):
        mock_user_state["messages"] = [
            HumanMessage(content="Stop sending me the weekly digest emails")
        ]
        result = supervisor_node(mock_user_state)
        response = _extract_response(result)

        assert any(kw in response for kw in OPT_OUT_KEYWORDS), (
            f"Expected opt-out confirmation keyword in response: {response[:500]}"
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_opt_in_confirms_action(
        self,
        mock_user_state: AgentState,
        mock_yahoo_and_notifications: None,
    ):
        mock_user_state["messages"] = [
            HumanMessage(content="Turn the weekly digest back on please")
        ]
        result = supervisor_node(mock_user_state)
        response = _extract_response(result)

        assert any(kw in response for kw in OPT_IN_KEYWORDS), (
            f"Expected opt-in confirmation keyword in response: {response[:500]}"
        )

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_unsubscribe_confirms_action(
        self,
        mock_user_state: AgentState,
        mock_yahoo_and_notifications: None,
    ):
        mock_user_state["messages"] = [
            HumanMessage(content="Unsubscribe me from the weekly emails")
        ]
        result = supervisor_node(mock_user_state)
        response = _extract_response(result)

        assert any(kw in response for kw in OPT_OUT_KEYWORDS), (
            f"Expected unsubscribe confirmation keyword in response: {response[:500]}"
        )
