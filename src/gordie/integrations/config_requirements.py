"""Shared environment-variable requirements for setup and startup."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConfigRequirement:
    key: str
    reason: str


def required_config_for_runtime(
    *,
    values: Mapping[str, str],
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
    requirements.extend(
        (
            ConfigRequirement("OPENROUTER_API_KEY", "required for OpenRouter models"),
            ConfigRequirement("LLM_MODEL", "required for the OpenRouter chat model"),
        )
    )
    return tuple(requirements)


def required_keys_for_runtime(
    *,
    values: Mapping[str, str],
    include_database_url: bool,
    include_admin_api_key: bool,
) -> tuple[str, ...]:
    return tuple(
        requirement.key
        for requirement in required_config_for_runtime(
            values=values,
            include_database_url=include_database_url,
            include_admin_api_key=include_admin_api_key,
        )
    )
