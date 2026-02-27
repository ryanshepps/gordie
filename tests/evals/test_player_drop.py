"""Player drop decision evals for fantasy hockey agent."""

from langchain_core.messages import HumanMessage

from agent.SupervisorAgent import supervisor_node
from tests.evals.conftest import retry_on_rate_limit

RECOMMENDATION_KEYWORDS = ("drop", "keep", "hold", "roster", "cut", "hang on", "let go")
STATS_KEYWORDS = ("goal", "point", "assist", "xgoal", "corsi", "fenwick", "production")
SCHEDULE_KEYWORDS = ("schedule", "games", "week", "matchup", "upcoming")


class TestPlayerDropDecision:

    @retry_on_rate_limit(max_retries=3, base_delay=2.0)
    def test_response_gives_recommendation_with_stats_and_schedule(
        self,
        mock_user_state,
        mock_yahoo_tools,
    ):
        mock_user_state["messages"] = [HumanMessage(content="Should I drop Timo Meier?")]
        result = supervisor_node(mock_user_state)

        update = result.update or {}
        response_text = update.get("response", "")
        response_lower = response_text.lower()

        assert any(kw in response_lower for kw in RECOMMENDATION_KEYWORDS), (
            f"Expected drop/keep/hold recommendation keyword: {response_text[:500]}"
        )
        assert any(kw in response_lower for kw in STATS_KEYWORDS), (
            f"Expected stats keyword in response: {response_text[:500]}"
        )
        assert any(kw in response_lower for kw in SCHEDULE_KEYWORDS), (
            f"Expected schedule keyword in response: {response_text[:500]}"
        )
