"""Shared environment-variable requirements for setup and startup."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum


class LLMProvider(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


@dataclass(frozen=True, slots=True)
class ConfigRequirement:
    key: str
    reason: str


def default_llm_model(provider: LLMProvider) -> str:
    if provider is LLMProvider.OPENAI:
        return "gpt-4o-mini"
    return "claude-sonnet-4-5"


def required_config_for_runtime(
    *,
    llm_provider: LLMProvider,
    values: Mapping[str, str],
    billing_enabled: bool,
    include_database_url: bool,
    include_admin_api_key: bool,
) -> tuple[ConfigRequirement, ...]:
    requirements: list[ConfigRequirement] = []
    if include_database_url:
        requirements.append(
            ConfigRequirement("DATABASE_URL", "required before database migrations can run")
        )
    if include_admin_api_key:
        requirements.append(
            ConfigRequirement("ADMIN_API_KEY", "required for setup-generated deployments")
        )
    requirements.extend(
        (
            ConfigRequirement("OAUTH_BASE_URL", "required for Yahoo OAuth callbacks"),
            ConfigRequirement("YAHOO_CLIENT_ID", "required for Yahoo Fantasy OAuth"),
            ConfigRequirement("YAHOO_CLIENT_SECRET", "required for Yahoo Fantasy OAuth"),
        )
    )
    if llm_provider is LLMProvider.OPENAI:
        requirements.append(
            ConfigRequirement("OPENAI_API_KEY", "required when LLM_PROVIDER=openai")
        )
    else:
        requirements.append(
            ConfigRequirement("ANTHROPIC_API_KEY", "required when LLM_PROVIDER=anthropic")
        )
    if billing_enabled:
        requirements.extend(
            (
                ConfigRequirement("CREEM_API_KEY", "required when Creem billing is enabled"),
                ConfigRequirement("CREEM_WEBHOOK_SECRET", "required when Creem billing is enabled"),
                ConfigRequirement(
                    "CREEM_PRODUCT_HOSTED_MONTHLY", "required when Creem billing is enabled"
                ),
            )
        )
    return tuple(requirements)


def required_keys_for_runtime(
    *,
    llm_provider: LLMProvider,
    values: Mapping[str, str],
    billing_enabled: bool,
    include_database_url: bool,
    include_admin_api_key: bool,
) -> tuple[str, ...]:
    return tuple(
        requirement.key
        for requirement in required_config_for_runtime(
            llm_provider=llm_provider,
            values=values,
            billing_enabled=billing_enabled,
            include_database_url=include_database_url,
            include_admin_api_key=include_admin_api_key,
        )
    )
