from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage

from agent.agent_state import AgentState
from agent.SupervisorAgent import _invoke_billing_response
from data.models import Medium


def _make_state(
    message: str = "hello",
    channel: Medium = Medium.EMAIL,
) -> AgentState:
    return AgentState(
        messages=[HumanMessage(content=message)],
        channel=channel,
        user_id="user-123",
        external_id="user@test.com",
        response=None,
        context_status="billing_blocked",
        billing_context="BILLING LIMIT REACHED",
    )


class TestInvokeBillingResponse:
    @patch("agent.SupervisorAgent.make_llm")
    @patch("agent.SupervisorAgent.assemble_system_prompt", return_value="system prompt")
    def test_returns_response_command_with_billing_message(self, mock_assemble, mock_llm_cls):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(
            content="You've hit your limit! Here are upgrade links."
        )
        mock_llm_cls.return_value = mock_llm

        state = _make_state("Should I start McDavid?")
        result = _invoke_billing_response(state)

        assert result.goto == "data_quality"
        assert result.update is not None
        assert result.update["response"] == "You've hit your limit! Here are upgrade links."

    @patch("agent.SupervisorAgent.make_llm")
    @patch("agent.SupervisorAgent.assemble_system_prompt", return_value="system prompt")
    def test_passes_state_to_assemble(self, mock_assemble, mock_llm_cls):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content="response")
        mock_llm_cls.return_value = mock_llm

        state = _make_state(channel=Medium.SMS)

        _invoke_billing_response(state)

        mock_assemble.assert_called_once_with(state)

    @patch("agent.SupervisorAgent.make_llm")
    @patch("agent.SupervisorAgent.assemble_system_prompt", return_value="system prompt")
    def test_skips_tools_for_billing_response(self, mock_assemble, mock_llm_cls):
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = AIMessage(content="upgrade please")
        mock_llm_cls.return_value = mock_llm

        state = _make_state("trade advice?")
        _invoke_billing_response(state)

        call_args = mock_llm.invoke.call_args[0][0]
        assert call_args[0]["role"] == "system"
        assert not mock_llm.bind_tools.called

    @patch("agent.SupervisorAgent.make_llm", side_effect=Exception("LLM error"))
    @patch("agent.SupervisorAgent.assemble_system_prompt", return_value="system prompt")
    def test_error_returns_fallback_response(self, mock_assemble, mock_llm_cls):
        state = _make_state()
        result = _invoke_billing_response(state)

        assert result.goto == "response"
        assert result.update is not None
        response_text: str = result.update["response"]
        assert "error" in response_text.lower()
