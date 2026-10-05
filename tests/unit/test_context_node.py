from unittest.mock import patch

from langchain_core.messages import HumanMessage

from gordie.agent.agent_state import AgentState
from gordie.agent.context_node import context_node
from gordie.data.models import Medium


def _make_state(**overrides) -> AgentState:
    defaults: AgentState = AgentState(
        messages=[HumanMessage(content="hello")],
        user_id="00000000-0000-0000-0000-000000000001",
        external_id="user@example.com",
        channel=Medium.EMAIL,
        thread_id="thread-1",
    )
    for k, v in overrides.items():
        defaults[k] = v
    return defaults


class TestAccessContext:
    @patch("gordie.agent.context_node.check_oauth_status", return_value=True)
    @patch("gordie.agent.context_node._fetch_onboarded_teams", return_value=[])
    @patch("gordie.agent.context_node.fetch_supported_teams", return_value=[])
    def test_clears_previous_denial_when_access_is_allowed(self, *_mocks):
        state = _make_state(access_context="Previous denial")

        result = context_node(state)

        assert result["context_status"] != "access_blocked"
        assert "access_context" in result
        assert result["access_context"] is None


class TestMissingUserId:
    def test_returns_error_when_no_user_id(self):
        state = _make_state(user_id="")

        result = context_node(state)

        assert result["context_status"] == "error"
        assert "user id" in result.get("context_error", "").lower()


class TestNoOAuth:
    @patch("gordie.agent.context_node.generate_oauth_link")
    @patch("gordie.agent.memory_store.get_memory_store")
    @patch("gordie.agent.context_node.is_first_time_user", return_value=True)
    @patch("gordie.agent.context_node.check_oauth_status", return_value=False)
    def test_first_time_user_returns_first_time_status(
        self, _mock_oauth_check, _mock_first_time, _mock_memory_store, mock_gen_link
    ):
        mock_gen_link.invoke.return_value = "https://yahoo.com/oauth"
        state = _make_state()

        result = context_node(state)

        assert result["context_status"] == "first_time_user"
        assert result.get("oauth_url") == "https://yahoo.com/oauth"

    @patch("gordie.agent.context_node.generate_oauth_link")
    @patch("gordie.agent.memory_store.get_memory_store")
    @patch("gordie.agent.context_node.is_first_time_user", return_value=False)
    @patch("gordie.agent.context_node.check_oauth_status", return_value=False)
    def test_returning_user_no_oauth_returns_no_oauth_status(
        self, _mock_oauth_check, _mock_first_time, _mock_memory_store, mock_gen_link
    ):
        mock_gen_link.invoke.return_value = "https://yahoo.com/oauth"
        state = _make_state()

        result = context_node(state)

        assert result["context_status"] == "no_oauth"
        assert result.get("oauth_url") == "https://yahoo.com/oauth"


class TestNoTeamsInDb:
    @patch("gordie.agent.context_node._handle_no_teams")
    @patch("gordie.agent.context_node._fetch_onboarded_teams", return_value=[])
    @patch("gordie.agent.context_node.check_oauth_status", return_value=True)
    def test_delegates_to_handle_no_teams(self, _mock_oauth, _mock_fetch, mock_handle):
        mock_handle.return_value = {"context_status": "no_teams_available"}
        state = _make_state()

        result = context_node(state)

        assert result["context_status"] == "no_teams_available"
        mock_handle.assert_called_once_with("00000000-0000-0000-0000-000000000001")


class TestTeamAmbiguous:
    @patch("gordie.agent.context_node.resolve_team_context", return_value=(None, None))
    @patch("gordie.agent.context_node._fetch_onboarded_teams")
    @patch("gordie.agent.context_node.check_oauth_status", return_value=True)
    def test_multiple_teams_no_resolution_returns_ambiguous(
        self, _mock_oauth, mock_fetch, _mock_resolve
    ):
        teams = [
            {"league_id": "1", "team_id": "1", "team_name": "A", "league_name": "L1"},
            {"league_id": "2", "team_id": "2", "team_name": "B", "league_name": "L2"},
        ]
        mock_fetch.return_value = teams
        state = _make_state()

        result = context_node(state)

        assert result["context_status"] == "team_ambiguous"
        assert result.get("available_teams") == teams


class TestValidated:
    @patch("gordie.agent.context_node.resolve_team_context", return_value=("123", "456"))
    @patch("gordie.agent.context_node._fetch_onboarded_teams")
    @patch("gordie.agent.context_node.check_oauth_status", return_value=True)
    def test_validated_context_returns_league_and_team(
        self, _mock_oauth, mock_fetch, _mock_resolve
    ):
        teams = [{"league_id": "123", "team_id": "456", "game_key": "465", "sport": "nhl"}]
        mock_fetch.return_value = teams
        state = _make_state()

        result = context_node(state)

        assert result["context_status"] == "validated"
        assert result.get("league_id") == "123"
        assert result.get("team_id") == "456"
        assert result.get("sport") == "nhl"

    @patch("gordie.agent.context_node.resolve_team_context", return_value=("789", "101"))
    @patch("gordie.agent.context_node._fetch_onboarded_teams")
    @patch("gordie.agent.context_node.check_oauth_status", return_value=True)
    def test_infers_sport_from_team_data(self, _mock_oauth, mock_fetch, _mock_resolve):
        teams = [{"league_id": "789", "team_id": "101", "game_key": "450", "sport": "nfl"}]
        mock_fetch.return_value = teams
        state = _make_state()

        result = context_node(state)

        assert result["context_status"] == "validated"
        assert result.get("sport") == "nfl"

    @patch("gordie.agent.context_node.resolve_team_context", return_value=("111", "222"))
    @patch("gordie.agent.context_node.fetch_supported_teams", return_value=[])
    @patch("gordie.agent.context_node._fetch_onboarded_teams")
    @patch("gordie.agent.context_node.check_oauth_status", return_value=True)
    def test_unsupported_saved_team_requires_onboarding(
        self, _mock_oauth, mock_fetch, _mock_available, _mock_resolve
    ):
        teams = [{"league_id": "111", "team_id": "222", "game_key": "999", "sport": "mlb"}]
        mock_fetch.return_value = teams
        state = _make_state()

        result = context_node(state)

        assert result["context_status"] == "no_teams_available"
        assert result.get("league_id") is None
        assert result.get("sport") is None

    @patch("gordie.agent.context_node._fetch_onboarded_teams")
    @patch("gordie.agent.context_node.check_oauth_status", return_value=True)
    def test_stale_team_selection_cannot_validate_an_unsupported_saved_team(
        self, _mock_oauth, mock_fetch
    ):
        mock_fetch.return_value = [
            {"league_id": "111", "team_id": "222", "sport": "mlb"},
            {"league_id": "123", "team_id": "456", "sport": "nhl"},
        ]
        state = _make_state(league_id="111", team_id="222")

        result = context_node(state)

        assert result["context_status"] == "validated"
        assert result.get("league_id") == "123"
        assert result.get("team_id") == "456"
        assert result.get("sport") == "nhl"

    @patch("gordie.agent.context_node.resolve_team_context", return_value=("123", "456"))
    @patch("gordie.agent.context_node._fetch_onboarded_teams")
    @patch("gordie.agent.context_node.check_oauth_status", return_value=True)
    def test_validated_result_includes_sport_inferred_at(
        self, _mock_oauth, mock_fetch, _mock_resolve
    ):
        teams = [{"league_id": "123", "team_id": "456", "game_key": "465", "sport": "nhl"}]
        mock_fetch.return_value = teams
        state = _make_state()

        result = context_node(state)

        assert result["context_status"] == "validated"
        assert "sport_inferred_at" in result


class TestSportInference:
    @patch("gordie.agent.context_node.resolve_team_context", return_value=(None, None))
    @patch("gordie.agent.context_node._fetch_onboarded_teams")
    @patch("gordie.agent.context_node.check_oauth_status", return_value=True)
    def test_keyword_narrows_to_single_team(self, _mock_oauth, mock_fetch, _mock_resolve):
        teams = [
            {
                "league_id": "1",
                "team_id": "10",
                "team_name": "A",
                "league_name": "L1",
                "sport": "nhl",
            },
            {
                "league_id": "2",
                "team_id": "20",
                "team_name": "B",
                "league_name": "L2",
                "sport": "nfl",
            },
        ]
        mock_fetch.return_value = teams
        state = _make_state(messages=[HumanMessage(content="how's my football team")])

        result = context_node(state)

        assert result["context_status"] == "validated"
        assert result.get("sport") == "nfl"
        assert result.get("league_id") == "2"
        assert result.get("team_id") == "20"

    @patch("gordie.agent.context_node.resolve_team_context", return_value=(None, None))
    @patch("gordie.agent.context_node._fetch_onboarded_teams")
    @patch("gordie.agent.context_node.check_oauth_status", return_value=True)
    def test_keyword_narrows_to_sport_but_multiple_teams_returns_ambiguous(
        self, _mock_oauth, mock_fetch, _mock_resolve
    ):
        teams = [
            {
                "league_id": "1",
                "team_id": "10",
                "team_name": "A",
                "league_name": "L1",
                "sport": "nfl",
            },
            {
                "league_id": "2",
                "team_id": "20",
                "team_name": "B",
                "league_name": "L2",
                "sport": "nfl",
            },
        ]
        mock_fetch.return_value = teams
        state = _make_state(messages=[HumanMessage(content="how's my football team")])

        result = context_node(state)

        assert result["context_status"] == "team_ambiguous"

    @patch("gordie.agent.context_node.resolve_team_context", return_value=(None, None))
    @patch("gordie.agent.context_node._fetch_onboarded_teams")
    @patch("gordie.agent.context_node.check_oauth_status", return_value=True)
    def test_no_sport_signal_returns_ambiguous(self, _mock_oauth, mock_fetch, _mock_resolve):
        teams = [
            {
                "league_id": "1",
                "team_id": "10",
                "team_name": "A",
                "league_name": "L1",
                "sport": "nhl",
            },
            {
                "league_id": "2",
                "team_id": "20",
                "team_name": "B",
                "league_name": "L2",
                "sport": "nfl",
            },
        ]
        mock_fetch.return_value = teams
        state = _make_state(messages=[HumanMessage(content="hello")])

        result = context_node(state)

        assert result["context_status"] == "team_ambiguous"
