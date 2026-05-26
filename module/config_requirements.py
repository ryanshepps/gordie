"""Shared environment-variable requirement rules for setup and startup."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum


class ChatMedium(StrEnum):
    TELEGRAM = "telegram"
    DISCORD = "discord"
    EMAIL = "email"
    SMS = "sms"


class LLMProvider(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class DiscordMode(StrEnum):
    GATEWAY = "gateway"
    INTERACTIONS = "interactions"


@dataclass(frozen=True, slots=True)
class ConfigRequirement:
    key: str
    reason: str


def chat_medium_values() -> str:
    """Return chat medium choices for prompts and error messages."""
    return ", ".join(medium.value for medium in ChatMedium)


def parse_chat_media_values(raw_value: str, *, require_non_empty: bool) -> tuple[ChatMedium, ...]:
    """Parse comma-separated chat media without UI-specific error types."""
    values = [value.strip().lower() for value in raw_value.split(",") if value.strip()]
    if not values:
        if require_non_empty:
            raise ValueError("Choose at least one chat medium.")
        return ()

    media: list[ChatMedium] = []
    invalid: list[str] = []
    for value in values:
        try:
            medium = ChatMedium(value)
        except ValueError:
            invalid.append(value)
            continue
        if medium not in media:
            media.append(medium)

    if invalid:
        invalid_list = ", ".join(invalid)
        raise ValueError(
            f"Unknown chat medium: {invalid_list}. Choose from: {chat_medium_values()}."
        )

    return tuple(media)


def default_llm_model(provider: LLMProvider) -> str:
    """Return the setup wizard's default model for the selected provider."""
    if provider is LLMProvider.OPENAI:
        return "gpt-4o-mini"
    return "claude-sonnet-4-5"


def required_config_for_runtime(
    *,
    llm_provider: LLMProvider,
    chat_media: Sequence[ChatMedium],
    values: Mapping[str, str],
    billing_enabled: bool,
    include_database_url: bool,
    include_admin_api_key: bool,
) -> tuple[ConfigRequirement, ...]:
    """Return required environment variables for the selected runtime path."""
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
    requirements.extend(_llm_required_config(llm_provider))
    requirements.extend(_medium_required_config(chat_media, values))
    requirements.extend(_billing_required_config(billing_enabled))
    return tuple(requirements)


def required_keys_for_runtime(
    *,
    llm_provider: LLMProvider,
    chat_media: Sequence[ChatMedium],
    values: Mapping[str, str],
    billing_enabled: bool,
    include_database_url: bool,
    include_admin_api_key: bool,
) -> tuple[str, ...]:
    """Return only the variable names required for the selected runtime path."""
    return tuple(
        requirement.key
        for requirement in required_config_for_runtime(
            llm_provider=llm_provider,
            chat_media=chat_media,
            values=values,
            billing_enabled=billing_enabled,
            include_database_url=include_database_url,
            include_admin_api_key=include_admin_api_key,
        )
    )


def _llm_required_config(provider: LLMProvider) -> tuple[ConfigRequirement, ...]:
    if provider is LLMProvider.OPENAI:
        return (ConfigRequirement("OPENAI_API_KEY", "required when LLM_PROVIDER=openai"),)
    return (ConfigRequirement("ANTHROPIC_API_KEY", "required when LLM_PROVIDER=anthropic"),)


def _medium_required_config(
    media: Sequence[ChatMedium],
    values: Mapping[str, str],
) -> tuple[ConfigRequirement, ...]:
    required: list[ConfigRequirement] = []
    for medium in media:
        if medium is ChatMedium.TELEGRAM:
            required.append(
                ConfigRequirement(
                    "TELEGRAM_BOT_TOKEN",
                    "required when CHAT_MEDIA includes telegram",
                )
            )
        elif medium is ChatMedium.DISCORD:
            required.extend(discord_required_config(values))
        elif medium is ChatMedium.EMAIL:
            required.extend(
                (
                    ConfigRequirement(
                        "MAILGUN_API_KEY",
                        "required when CHAT_MEDIA includes email",
                    ),
                    ConfigRequirement(
                        "MAILGUN_DOMAIN",
                        "required when CHAT_MEDIA includes email",
                    ),
                    ConfigRequirement(
                        "MAILGUN_FROM_EMAIL",
                        "required when CHAT_MEDIA includes email",
                    ),
                    ConfigRequirement(
                        "MAILGUN_WEBHOOK_SIGNING_KEY",
                        "required when CHAT_MEDIA includes email",
                    ),
                )
            )
        else:
            required.extend(
                (
                    ConfigRequirement(
                        "SINCH_SERVICE_PLAN_ID",
                        "required when CHAT_MEDIA includes sms",
                    ),
                    ConfigRequirement("SINCH_API_TOKEN", "required when CHAT_MEDIA includes sms"),
                    ConfigRequirement("SINCH_FROM_NUMBER", "required when CHAT_MEDIA includes sms"),
                    ConfigRequirement(
                        "SINCH_WEBHOOK_TOKEN",
                        "required when CHAT_MEDIA includes sms",
                    ),
                )
            )
    return tuple(required)


def discord_required_config(values: Mapping[str, str]) -> tuple[ConfigRequirement, ...]:
    mode = values.get("DISCORD_MODE", DiscordMode.GATEWAY.value).strip().lower()
    if mode == DiscordMode.INTERACTIONS.value:
        return (
            ConfigRequirement("DISCORD_MODE", "required when CHAT_MEDIA includes discord"),
            ConfigRequirement(
                "DISCORD_APPLICATION_ID",
                "required when CHAT_MEDIA includes discord",
            ),
            ConfigRequirement(
                "DISCORD_PUBLIC_KEY",
                "required when DISCORD_MODE=interactions",
            ),
        )
    return (
        ConfigRequirement("DISCORD_MODE", "required when CHAT_MEDIA includes discord"),
        ConfigRequirement(
            "DISCORD_APPLICATION_ID",
            "required when CHAT_MEDIA includes discord",
        ),
        ConfigRequirement("DISCORD_BOT_TOKEN", "required when DISCORD_MODE=gateway"),
        ConfigRequirement(
            "DISCORD_ALLOWED_USER_IDS",
            "required when DISCORD_MODE=gateway",
        ),
    )


def _billing_required_config(billing_enabled: bool) -> tuple[ConfigRequirement, ...]:
    if not billing_enabled:
        return ()
    return (
        ConfigRequirement("CREEM_API_KEY", "required when Creem billing is enabled"),
        ConfigRequirement("CREEM_WEBHOOK_SECRET", "required when Creem billing is enabled"),
        ConfigRequirement(
            "CREEM_PRODUCT_HOSTED_MONTHLY",
            "required when Creem billing is enabled",
        ),
    )
