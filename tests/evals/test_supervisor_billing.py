"""Tests for supervisor billing context handling."""

from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from agent.agent_state import AgentState
from agent.SupervisorAgent import _invoke_billing_response


def _make_state(
    message: str = "hello",
    channel: str = "email",
) -> AgentState:
    return AgentState(
        messages=[HumanMessage(content=message)],
        channel=channel,
        response=None,
    )


class TestInvokeBillingResponse:
    @patch("agent.SupervisorAgent.ChatOpenAI")
    @patch("agent.SupervisorAgent.assemble_system_prompt", return_value="system prompt")
    def test_returns_response_command_with_billing_message(self, mock_assemble, mock_llm_cls):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(
            content="You've hit your limit! Here are upgrade links."
        )
        mock_llm_cls.return_value = mock_llm

        state = _make_state("Should I start McDavid?")
        result = _invoke_billing_response(state, "user@test.com", "BILLING LIMIT REACHED")

        assert result.goto == "response"
        assert result.update is not None
        assert result.update["response"] == "You've hit your limit! Here are upgrade links."

    @patch("agent.SupervisorAgent.ChatOpenAI")
    @patch("agent.SupervisorAgent.assemble_system_prompt", return_value="system prompt")
    def test_passes_billing_context_as_system_message(self, mock_assemble, mock_llm_cls):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content="response")
        mock_llm_cls.return_value = mock_llm

        billing_ctx = "BILLING LIMIT REACHED — user hit quota"
        state = _make_state(channel="sms")

        _invoke_billing_response(state, "user@test.com", billing_ctx)

        from agent.context_validator import ValidationResult

        mock_assemble.assert_called_once()
        validation_arg = mock_assemble.call_args[0][0]
        assert isinstance(validation_arg, ValidationResult)
        assert validation_arg.system_message == billing_ctx

    @patch("agent.SupervisorAgent.ChatOpenAI")
    @patch("agent.SupervisorAgent.assemble_system_prompt", return_value="system prompt")
    def test_skips_tools_for_billing_response(self, mock_assemble, mock_llm_cls):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content="upgrade please")
        mock_llm_cls.return_value = mock_llm

        state = _make_state("trade advice?")
        _invoke_billing_response(state, "user@test.com", "billing context")

        call_args = mock_llm.invoke.call_args[0][0]
        assert call_args[0]["role"] == "system"
        assert not mock_llm.bind_tools.called

    @patch("agent.SupervisorAgent.ChatOpenAI", side_effect=Exception("LLM error"))
    @patch("agent.SupervisorAgent.assemble_system_prompt", return_value="system prompt")
    def test_error_returns_fallback_response(self, mock_assemble, mock_llm_cls):
        state = _make_state()
        result = _invoke_billing_response(state, "user@test.com", "billing context")

        assert result.goto == "response"
        assert result.update is not None
        response_text: str = result.update["response"]
        assert "error" in response_text.lower()
