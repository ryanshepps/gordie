"""Tests for the LLM-powered digest content writer."""

from unittest.mock import MagicMock, patch

import pytest

from agent.digest_writer import DigestType, _build_system_prompt, write_digest_content
from agent.prompts.channel_guidelines import get_channel_guidelines
from agent.prompts.persona import PERSONA
from data.pydantic_models import DigestData, RosterPerformance


@pytest.fixture
def weekly_digest_data():
    return DigestData(
        league_name="Test League",
        team_name="My Team",
        current_week=15,
        roster_performance=RosterPerformance(),
    )


class TestBuildSystemPrompt:
    def test_includes_persona(self):
        prompt = _build_system_prompt(DigestType.WEEKLY)
        assert PERSONA in prompt

    def test_includes_email_channel_guidelines(self):
        prompt = _build_system_prompt(DigestType.WEEKLY)
        email_guidelines = get_channel_guidelines("email")
        assert email_guidelines in prompt

    def test_weekly_includes_weekly_instructions(self):
        prompt = _build_system_prompt(DigestType.WEEKLY)
        assert "600 words" in prompt

    def test_news_includes_news_instructions(self):
        prompt = _build_system_prompt(DigestType.NEWS)
        assert "400 words" in prompt

    def test_sms_channel_includes_sms_guidelines(self):
        prompt = _build_system_prompt(DigestType.WEEKLY, channel="sms")
        sms_guidelines = get_channel_guidelines("sms")
        assert sms_guidelines in prompt

    def test_weekly_sms_has_shorter_word_limit(self):
        prompt = _build_system_prompt(DigestType.WEEKLY, channel="sms")
        assert "200 words" in prompt

    def test_news_sms_has_shorter_word_limit(self):
        prompt = _build_system_prompt(DigestType.NEWS, channel="sms")
        assert "150 words" in prompt


class TestWriteDigestContent:
    @patch("agent.digest_writer.ChatOpenAI")
    def test_returns_llm_response(self, mock_chat_class, weekly_digest_data):
        mock_response = MagicMock()
        mock_response.content = "Hey buddy, here's your weekly update..."
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_response
        mock_chat_class.return_value = mock_llm

        result = write_digest_content(weekly_digest_data, DigestType.WEEKLY)

        assert result == "Hey buddy, here's your weekly update..."
        mock_chat_class.assert_called_once_with(model="gpt-4o-mini", temperature=0.7)
        mock_llm.invoke.assert_called_once()

    @patch("agent.digest_writer.ChatOpenAI")
    def test_passes_serialized_data_to_llm(self, mock_chat_class, weekly_digest_data):
        mock_response = MagicMock()
        mock_response.content = "digest content"
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = mock_response
        mock_chat_class.return_value = mock_llm

        write_digest_content(weekly_digest_data, DigestType.WEEKLY)

        call_args = mock_llm.invoke.call_args[0][0]
        assert call_args[0]["role"] == "system"
        assert PERSONA in call_args[0]["content"]
        assert call_args[1]["role"] == "user"
        assert "Test League" in call_args[1]["content"]

    @patch("agent.digest_writer.ChatOpenAI")
    def test_failure_propagates(self, mock_chat_class, weekly_digest_data):
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = RuntimeError("API error")
        mock_chat_class.return_value = mock_llm

        with pytest.raises(RuntimeError, match="API error"):
            write_digest_content(weekly_digest_data, DigestType.WEEKLY)
