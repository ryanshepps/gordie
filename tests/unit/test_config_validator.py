"""Tests for startup configuration validation."""

import pytest

from gordie.integrations.config_validator import ConfigValidationError, validate_startup_config


def _valid_env(**overrides: str) -> dict[str, str]:
    env = {
        "DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/fantasy_agent",
        "OAUTH_BASE_URL": "https://gordie.example",
        "YAHOO_CLIENT_ID": "yahoo-id",
        "YAHOO_CLIENT_SECRET": "yahoo-secret",
        "LLM_MODEL": "openai/gpt-4o-mini",
        "OPENROUTER_API_KEY": "sk-test",
        "SERVER_PORT": "8000",
    }
    env.update(overrides)
    return env


def test_validate_startup_config_lists_all_missing_required_values() -> None:
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_startup_config({})

    message = str(exc_info.value)
    assert "DATABASE_URL" in message
    assert "OAUTH_BASE_URL" in message
    assert "YAHOO_CLIENT_ID" in message
    assert "YAHOO_CLIENT_SECRET" in message
    assert "OPENROUTER_API_KEY" in message
    assert "LLM_MODEL" in message
    assert "uv run gordie init" in message


def test_validate_startup_config_accepts_valid_core_config() -> None:
    validate_startup_config(_valid_env())


def test_validate_startup_config_requires_openrouter_key() -> None:
    env = _valid_env(OPENROUTER_API_KEY="")

    with pytest.raises(ConfigValidationError) as exc_info:
        validate_startup_config(env)

    message = str(exc_info.value)
    assert "OPENROUTER_API_KEY" in message
    assert "sk-test" not in message


def test_validate_startup_config_requires_public_https_oauth_base_url() -> None:
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_startup_config(_valid_env(OAUTH_BASE_URL="http://localhost:8000"))

    assert "OAUTH_BASE_URL must be a public HTTPS URL" in str(exc_info.value)


def test_validate_startup_config_reports_invalid_values_together() -> None:
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_startup_config(
            _valid_env(
                LLM_MODEL="",
                SERVER_PORT="not-a-port",
            )
        )

    message = str(exc_info.value)
    assert "LLM_MODEL" in message
    assert "SERVER_PORT must be an integer from 1 to 65535" in message
