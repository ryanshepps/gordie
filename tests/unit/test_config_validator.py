"""Tests for startup configuration validation."""

import pytest

from gordie.module.config_validator import ConfigValidationError, validate_startup_config


def _valid_env(**overrides: str) -> dict[str, str]:
    env = {
        "DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/fantasy_agent",
        "OAUTH_BASE_URL": "https://gordie.example",
        "YAHOO_CLIENT_ID": "yahoo-id",
        "YAHOO_CLIENT_SECRET": "yahoo-secret",
        "LLM_PROVIDER": "openai",
        "OPENAI_API_KEY": "sk-test",
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
    assert "OPENAI_API_KEY" in message
    assert "uv run gordie init" in message


def test_validate_startup_config_accepts_valid_core_config() -> None:
    validate_startup_config(_valid_env())


def test_validate_startup_config_requires_anthropic_key_for_anthropic_provider() -> None:
    env = _valid_env(LLM_PROVIDER="anthropic", OPENAI_API_KEY="", ANTHROPIC_API_KEY="")

    with pytest.raises(ConfigValidationError) as exc_info:
        validate_startup_config(env)

    message = str(exc_info.value)
    assert "ANTHROPIC_API_KEY" in message
    assert "OPENAI_API_KEY" not in message


def test_validate_startup_config_requires_public_https_oauth_base_url() -> None:
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_startup_config(_valid_env(OAUTH_BASE_URL="http://localhost:8000"))

    assert "OAUTH_BASE_URL must be a public HTTPS URL" in str(exc_info.value)


def test_validate_startup_config_reports_invalid_values_together() -> None:
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_startup_config(
            _valid_env(
                LLM_PROVIDER="bogus",
                SERVER_PORT="not-a-port",
            )
        )

    message = str(exc_info.value)
    assert "LLM_PROVIDER must be one of: openai, anthropic" in message
    assert "SERVER_PORT must be an integer from 1 to 65535" in message


def test_validate_startup_config_requires_hosted_product_when_billing_enabled() -> None:
    with pytest.raises(ConfigValidationError) as exc_info:
        validate_startup_config(
            _valid_env(CREEM_API_KEY="creem-key", CREEM_WEBHOOK_SECRET="creem-webhook")
        )

    assert "CREEM_PRODUCT_HOSTED_MONTHLY" in str(exc_info.value)
