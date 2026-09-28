"""Fail-fast startup validation for environment-driven configuration."""

from __future__ import annotations

from collections.abc import Mapping

from module.config_requirements import (
    ConfigRequirement,
    LLMProvider,
    required_config_for_runtime,
)
from server.oauth_config import OAuthConfigurationError, normalize_oauth_base_url


class ConfigValidationError(RuntimeError):
    """Raised when startup configuration is incomplete or invalid."""

    def __init__(
        self,
        *,
        missing: tuple[ConfigRequirement, ...],
        invalid: tuple[str, ...],
    ) -> None:
        self.missing: tuple[ConfigRequirement, ...] = missing
        self.invalid: tuple[str, ...] = invalid
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        lines = ["Startup configuration is incomplete.", ""]
        if self.missing:
            lines.append("Missing required environment variables:")
            lines.extend(f"- {item.key} ({item.reason})" for item in self.missing)
            lines.append("")
        if self.invalid:
            lines.append("Invalid environment values:")
            lines.extend(f"- {item}" for item in self.invalid)
            lines.append("")
        lines.append("Run `uv run gordie init` or update `.env` before starting Gordie.")
        return "\n".join(lines)


def validate_startup_config(env: Mapping[str, str]) -> None:
    """Validate startup env before database and server side effects."""
    invalid: list[str] = []
    llm_provider = _parse_llm_provider(env, invalid)
    _validate_oauth_base_url(env, invalid)
    _validate_server_port(env, invalid)

    requirements: list[ConfigRequirement] = []
    if llm_provider is not None:
        requirements.extend(
            required_config_for_runtime(
                llm_provider=llm_provider,
                values=env,
                billing_enabled=bool(_env_value(env, "CREEM_API_KEY")),
                include_database_url=True,
                include_admin_api_key=False,
            )
        )

    missing = tuple(
        requirement
        for requirement in _dedupe_requirements(requirements)
        if not _env_value(env, requirement.key)
    )
    if missing or invalid:
        raise ConfigValidationError(missing=missing, invalid=tuple(invalid))


def _parse_llm_provider(env: Mapping[str, str], invalid: list[str]) -> LLMProvider | None:
    raw_value = _env_value(env, "LLM_PROVIDER") or LLMProvider.OPENAI.value
    try:
        return LLMProvider(raw_value.lower())
    except ValueError:
        choices = ", ".join(provider.value for provider in LLMProvider)
        invalid.append(f"LLM_PROVIDER must be one of: {choices}.")
        return None


def _validate_oauth_base_url(env: Mapping[str, str], invalid: list[str]) -> None:
    raw_value = _env_value(env, "OAUTH_BASE_URL")
    if not raw_value:
        return
    try:
        _ = normalize_oauth_base_url(raw_value)
    except OAuthConfigurationError as exc:
        invalid.append(str(exc))


def _validate_server_port(env: Mapping[str, str], invalid: list[str]) -> None:
    raw_port = _env_value(env, "SERVER_PORT") or "8000"
    try:
        port = int(raw_port)
    except ValueError:
        invalid.append("SERVER_PORT must be an integer from 1 to 65535.")
        return
    if port < 1 or port > 65535:
        invalid.append("SERVER_PORT must be an integer from 1 to 65535.")


def _dedupe_requirements(
    requirements: list[ConfigRequirement],
) -> tuple[ConfigRequirement, ...]:
    seen: set[str] = set()
    deduped: list[ConfigRequirement] = []
    for requirement in requirements:
        if requirement.key in seen:
            continue
        seen.add(requirement.key)
        deduped.append(requirement)
    return tuple(deduped)


def _env_value(env: Mapping[str, str], key: str) -> str:
    return env.get(key, "").strip()
