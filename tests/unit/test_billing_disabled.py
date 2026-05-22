"""Tests verifying billing is fully disabled when no Creem keys are set."""

import importlib
from unittest.mock import MagicMock, patch


class TestBillingDisabledWhenNoKeys:
    def test_billing_enabled_false_without_creem_key(self):
        with patch.dict("os.environ", {}, clear=False):
            # Ensure CREEM_API_KEY is absent
            env = {"CREEM_API_KEY": "", "CREEM_WEBHOOK_SECRET": ""}
            with patch.dict("os.environ", env):
                import billing

                importlib.reload(billing)
                assert billing.billing_enabled is False

    def test_get_gateway_returns_null_without_creem_key(self):
        from billing import get_gateway
        from billing.gateway import NullBillingGateway

        with patch("billing.billing_enabled", False):
            gateway = get_gateway()
            assert isinstance(gateway, NullBillingGateway)

    def test_null_gateway_allows_all_questions(self):
        from billing.gateway import NullBillingGateway

        gw = NullBillingGateway()
        allowed, reason = gw.check_question_allowed("user@test.com", "Who should I start?")
        assert allowed is True
        assert reason == ""

    def test_null_gateway_allows_all_usage(self):
        from billing.gateway import NullBillingGateway

        gw = NullBillingGateway()
        allowed, reason = gw.check_usage_allowed("user@test.com", "digest")
        assert allowed is True
        assert reason == ""

    def test_null_gateway_allows_all_leagues(self):
        from billing.gateway import NullBillingGateway

        gw = NullBillingGateway()
        allowed, reason = gw.check_league_limit("user@test.com")
        assert allowed is True
        assert reason == ""

    def test_null_gateway_returns_free_tier(self):
        from billing.gateway import NullBillingGateway

        gw = NullBillingGateway()
        assert gw.get_user_tier("user@test.com") == "free"

    def test_null_gateway_billing_context_is_empty(self):
        from billing.gateway import NullBillingGateway

        gw = NullBillingGateway()
        ctx = gw.build_billing_context("user@test.com", "limit hit", "email")
        assert ctx == ""

    def test_billing_tools_absent_from_supervisor_when_disabled(self):
        # agent.subagents.{trade,available,statistician} call ChatOpenAI() at module
        # level, which raises without OPENAI_API_KEY. Patch it first so the import
        # triggered by the billing_enabled patch below succeeds.
        with (
            patch("agent.subagents.base.ChatOpenAI"),
            patch("agent.SupervisorAgent.billing_enabled", False),
            patch("agent.SupervisorAgent.create_agent") as mock_create,
            patch("agent.SupervisorAgent.make_llm", return_value=MagicMock()),
            patch("agent.memory_store.get_memory_store", return_value=MagicMock()),
            patch(
                "agent.SupervisorAgent.create_search_past_conversations_tool",
                return_value=MagicMock(name="search_past_conversations"),
            ),
        ):
            import agent.SupervisorAgent as SupervisorAgent

            mock_create.return_value = MagicMock()
            SupervisorAgent.create_supervisor_agent("system prompt")

            tools_passed = mock_create.call_args.kwargs["tools"]
            tool_names = [getattr(t, "name", str(t)) for t in tools_passed]

            assert "get_subscription_status" not in tool_names
            assert "generate_checkout_link" not in tool_names
            assert "generate_portal_link" not in tool_names

    def test_validate_billing_config_passes_with_no_keys(self):
        from billing import validate_billing_config

        with patch.dict("os.environ", {"CREEM_API_KEY": "", "CREEM_WEBHOOK_SECRET": ""}):
            # Should not raise
            validate_billing_config()
