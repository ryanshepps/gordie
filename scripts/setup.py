"""Interactive setup wizard for self-hosting Gordie."""

from __future__ import annotations

import re
import secrets
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Final, cast

import typer

app = typer.Typer(help="Gordie developer and self-hosting utilities.")


class SetupInputError(ValueError):
    """Raised when setup input cannot produce a valid .env file."""


class DeploymentTarget(StrEnum):
    DOCKER = "docker"


class ChatMedium(StrEnum):
    TELEGRAM = "telegram"
    DISCORD = "discord"
    EMAIL = "email"
    SMS = "sms"


class LLMProvider(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


@dataclass(frozen=True, slots=True)
class SetupAnswers:
    deployment_target: DeploymentTarget
    chat_media: tuple[ChatMedium, ...]
    llm_provider: LLMProvider
    values: Mapping[str, str]
    hosted: bool


_ENV_ASSIGNMENT_RE = re.compile(r"^([A-Z][A-Z0-9_]*)=(.*?)(\s+#.*)?$")
_CHAT_MEDIUM_VALUES = ", ".join(medium.value for medium in ChatMedium)
_YAHOO_APP_URL = "https://developer.yahoo.com/apps/"
_DEFAULT_ENV_FILE: Final = Path(".env")
_DEFAULT_TEMPLATE_FILE: Final = Path(".env.example")


@app.callback()
def main() -> None:
    """Run Gordie setup utilities."""


def parse_chat_media(raw_value: str) -> tuple[ChatMedium, ...]:
    """Parse a comma-separated chat medium list in user-entered order."""

    values = [value.strip().lower() for value in raw_value.split(",") if value.strip()]
    if not values:
        raise SetupInputError("Choose at least one chat medium.")

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
        raise SetupInputError(
            f"Unknown chat medium: {invalid_list}. Choose from: {_CHAT_MEDIUM_VALUES}."
        )

    return tuple(media)


def build_env_values(
    answers: SetupAnswers,
    *,
    admin_api_key: str | None = None,
) -> dict[str, str]:
    """Build the env key/value map written by the setup wizard."""

    values = {
        "DATABASE_URL": "postgresql://postgres:postgres@postgres:5432/fantasy_agent",
        "ADMIN_API_KEY": admin_api_key or secrets.token_hex(32),
        "ENVIRONMENT": "development",
        "OAUTH_BASE_URL": answers.values["OAUTH_BASE_URL"],
        "CHAT_MEDIA": ",".join(medium.value for medium in answers.chat_media),
        "LLM_PROVIDER": answers.llm_provider.value,
        "LLM_MODEL": _default_llm_model(answers.llm_provider),
        "OPENAI_API_KEY": "",
        "ANTHROPIC_API_KEY": "",
        "YAHOO_CLIENT_ID": answers.values["YAHOO_CLIENT_ID"],
        "YAHOO_CLIENT_SECRET": answers.values["YAHOO_CLIENT_SECRET"],
        "ENABLED_SPORTS": "nhl,mlb",
    }

    if answers.llm_provider is LLMProvider.OPENAI:
        values["OPENAI_API_KEY"] = answers.values["OPENAI_API_KEY"]
    else:
        values["ANTHROPIC_API_KEY"] = answers.values["ANTHROPIC_API_KEY"]

    for medium in answers.chat_media:
        values.update(_medium_env_values(medium, answers.values))

    if answers.hosted:
        values.update(
            {
                "CREEM_API_KEY": answers.values["CREEM_API_KEY"],
                "CREEM_WEBHOOK_SECRET": answers.values["CREEM_WEBHOOK_SECRET"],
                "CREEM_API_BASE_URL": answers.values["CREEM_API_BASE_URL"],
                "CREEM_PRODUCT_STANDARD_MONTHLY": answers.values["CREEM_PRODUCT_STANDARD_MONTHLY"],
                "CREEM_PRODUCT_STANDARD_ANNUAL": answers.values["CREEM_PRODUCT_STANDARD_ANNUAL"],
                "CREEM_PRODUCT_ALLSTAR_MONTHLY": answers.values["CREEM_PRODUCT_ALLSTAR_MONTHLY"],
                "CREEM_PRODUCT_ALLSTAR_ANNUAL": answers.values["CREEM_PRODUCT_ALLSTAR_ANNUAL"],
            }
        )
    else:
        values.update(
            {
                "CREEM_API_KEY": "",
                "CREEM_WEBHOOK_SECRET": "",
                "CREEM_API_BASE_URL": "https://test-api.creem.io/v1",
                "CREEM_PRODUCT_STANDARD_MONTHLY": "",
                "CREEM_PRODUCT_STANDARD_ANNUAL": "",
                "CREEM_PRODUCT_ALLSTAR_MONTHLY": "",
                "CREEM_PRODUCT_ALLSTAR_ANNUAL": "",
            }
        )

    _validate_required_values(values, answers)
    return values


def render_env_file(template_text: str, values: Mapping[str, str]) -> str:
    """Render .env content while preserving comments and unknown template lines."""

    rendered_lines: list[str] = []
    seen_keys: set[str] = set()

    for line in template_text.splitlines():
        match = _ENV_ASSIGNMENT_RE.match(line)
        if match is None:
            rendered_lines.append(line)
            continue

        key, _old_value, comment = match.groups()
        if key not in values:
            rendered_lines.append(line)
            continue

        suffix = f" {comment.lstrip()}" if comment else ""
        rendered_lines.append(f"{key}={_serialize_env_value(values[key])}{suffix}")
        seen_keys.add(key)

    missing_items = [(key, value) for key, value in values.items() if key not in seen_keys]
    if missing_items:
        if rendered_lines and rendered_lines[-1] != "":
            rendered_lines.append("")
        rendered_lines.extend(
            [
                "# ----------------------------------------------------------------------------",
                "# Setup CLI generated",
                "# ----------------------------------------------------------------------------",
            ]
        )
        rendered_lines.extend(
            f"{key}={_serialize_env_value(value)}" for key, value in missing_items
        )

    return "\n".join(rendered_lines) + "\n"


@app.command("init")
def init(
    hosted: Annotated[
        bool,
        typer.Option(
            "--hosted",
            help="Prompt for hosted billing credentials. Self-hosted setup skips billing.",
        ),
    ] = False,
    env_file: Annotated[
        Path,
        typer.Option("--env-file", help="Path to write the generated dotenv file."),
    ] = _DEFAULT_ENV_FILE,
    template_file: Annotated[
        Path,
        typer.Option("--template-file", help="Dotenv template to populate."),
    ] = _DEFAULT_TEMPLATE_FILE,
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite an existing dotenv file."),
    ] = False,
    skip_docker_check: Annotated[
        bool,
        typer.Option("--skip-docker-check", help="Skip Docker detection.", hidden=True),
    ] = False,
) -> None:
    """Create a local .env file through an interactive setup wizard."""

    try:
        if env_file.exists() and not force:
            raise SetupInputError(f"{env_file} already exists. Re-run with --force to overwrite.")
        if not template_file.exists():
            raise SetupInputError(f"{template_file} does not exist.")

        answers = _prompt_for_answers(hosted=hosted, skip_docker_check=skip_docker_check)
        env_text = render_env_file(template_file.read_text(), build_env_values(answers))
        _ = env_file.write_text(env_text)
    except SetupInputError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    typer.secho(f"Wrote {env_file}", fg=typer.colors.GREEN)
    typer.echo("")
    typer.echo("Next step:")
    typer.echo("  docker compose up -d")
    typer.echo("")
    typer.echo("Then run:")
    typer.echo("  docker compose exec server uv run alembic upgrade head")


def _prompt_for_answers(*, hosted: bool, skip_docker_check: bool) -> SetupAnswers:
    typer.echo("Gordie setup")
    typer.echo("")

    deployment_target = _prompt_enum(
        "Deployment target",
        DeploymentTarget,
        default=DeploymentTarget.DOCKER,
    )
    if deployment_target is DeploymentTarget.DOCKER and not skip_docker_check:
        _validate_docker_available()

    typer.echo(f"Chat media choices: {_CHAT_MEDIUM_VALUES}")
    chat_media = _prompt_chat_media()

    llm_provider = _prompt_enum("LLM provider", LLMProvider, default=LLMProvider.OPENAI)

    values: dict[str, str] = {
        "OAUTH_BASE_URL": _prompt_text("OAuth base URL", default="http://localhost:8000"),
    }
    values.update(_prompt_llm_values(llm_provider))

    typer.echo("")
    typer.echo(f"Create a Yahoo app at {_YAHOO_APP_URL}")
    typer.echo("Use this callback URL when Yahoo asks for a redirect URI:")
    typer.echo(f"  {values['OAUTH_BASE_URL'].rstrip('/')}/callback")
    values["YAHOO_CLIENT_ID"] = _prompt_required("Yahoo client ID")
    values["YAHOO_CLIENT_SECRET"] = _prompt_required("Yahoo client secret", hide_input=True)

    for medium in chat_media:
        values.update(_prompt_medium_values(medium))

    if hosted:
        values.update(_prompt_billing_values())

    return SetupAnswers(
        deployment_target=deployment_target,
        chat_media=chat_media,
        llm_provider=llm_provider,
        values=values,
        hosted=hosted,
    )


def _prompt_chat_media() -> tuple[ChatMedium, ...]:
    while True:
        raw_value = _prompt_text("Chat media", default=ChatMedium.TELEGRAM.value)
        try:
            return parse_chat_media(raw_value)
        except SetupInputError as exc:
            typer.secho(str(exc), fg=typer.colors.RED)


def _prompt_llm_values(provider: LLMProvider) -> dict[str, str]:
    if provider is LLMProvider.OPENAI:
        return {"OPENAI_API_KEY": _prompt_required("OpenAI API key", hide_input=True)}

    return {"ANTHROPIC_API_KEY": _prompt_required("Anthropic API key", hide_input=True)}


def _prompt_medium_values(medium: ChatMedium) -> dict[str, str]:
    typer.echo("")
    if medium is ChatMedium.TELEGRAM:
        typer.echo("Telegram setup")
        return {"TELEGRAM_BOT_TOKEN": _prompt_required("Telegram bot token", hide_input=True)}

    if medium is ChatMedium.DISCORD:
        typer.echo("Discord setup")
        return {
            "DISCORD_APPLICATION_ID": _prompt_required("Discord application ID"),
            "DISCORD_PUBLIC_KEY": _prompt_required("Discord public key", hide_input=True),
            "DISCORD_BOT_TOKEN": _prompt_required("Discord bot token", hide_input=True),
        }

    if medium is ChatMedium.EMAIL:
        typer.echo("Email setup (Mailgun)")
        domain = _prompt_required("Mailgun domain")
        return {
            "MAILGUN_API_KEY": _prompt_required("Mailgun API key", hide_input=True),
            "MAILGUN_DOMAIN": domain,
            "MAILGUN_FROM_EMAIL": _prompt_text(
                "Mailgun from email",
                default=f"Gordie <gordie@{domain}>",
            ),
            "MAILGUN_WEBHOOK_SIGNING_KEY": _prompt_required(
                "Mailgun webhook signing key",
                hide_input=True,
            ),
        }

    typer.echo("SMS setup (Sinch)")
    return {
        "SINCH_SERVICE_PLAN_ID": _prompt_required("Sinch service plan ID"),
        "SINCH_API_TOKEN": _prompt_required("Sinch API token", hide_input=True),
        "SINCH_FROM_NUMBER": _prompt_required("Sinch from number"),
        "SINCH_WEBHOOK_TOKEN": _prompt_required("Sinch webhook token", hide_input=True),
    }


def _prompt_billing_values() -> dict[str, str]:
    typer.echo("")
    typer.echo("Hosted billing setup (Creem)")
    return {
        "CREEM_API_KEY": _prompt_required("Creem API key", hide_input=True),
        "CREEM_WEBHOOK_SECRET": _prompt_required("Creem webhook secret", hide_input=True),
        "CREEM_API_BASE_URL": _prompt_text(
            "Creem API base URL",
            default="https://test-api.creem.io/v1",
        ),
        "CREEM_PRODUCT_STANDARD_MONTHLY": _prompt_required("Creem standard monthly product ID"),
        "CREEM_PRODUCT_STANDARD_ANNUAL": _prompt_required("Creem standard annual product ID"),
        "CREEM_PRODUCT_ALLSTAR_MONTHLY": _prompt_required("Creem all-star monthly product ID"),
        "CREEM_PRODUCT_ALLSTAR_ANNUAL": _prompt_required("Creem all-star annual product ID"),
    }


def _prompt_enum[T: StrEnum](
    label: str,
    enum_type: type[T],
    *,
    default: T,
) -> T:
    choices = ", ".join(item.value for item in enum_type)
    while True:
        raw_value = _prompt_text(f"{label} ({choices})", default=default.value)
        normalized = raw_value.strip().lower()
        try:
            return enum_type(normalized)
        except ValueError:
            typer.secho(f"Choose one of: {choices}.", fg=typer.colors.RED)


def _prompt_required(label: str, *, hide_input: bool = False) -> str:
    while True:
        value = _prompt_text(label, hide_input=hide_input).strip()
        if value:
            return value
        typer.secho(f"{label} is required.", fg=typer.colors.RED)


def _prompt_text(
    label: str,
    *,
    default: str | None = None,
    hide_input: bool = False,
) -> str:
    if default is None:
        prompted = cast(object, typer.prompt(label, hide_input=hide_input))
    else:
        prompted = cast(object, typer.prompt(label, default=default, hide_input=hide_input))
    if isinstance(prompted, str):
        return prompted
    return str(prompted)


def _medium_env_values(medium: ChatMedium, values: Mapping[str, str]) -> dict[str, str]:
    if medium is ChatMedium.TELEGRAM:
        return {"TELEGRAM_BOT_TOKEN": values["TELEGRAM_BOT_TOKEN"]}
    if medium is ChatMedium.DISCORD:
        return {
            "DISCORD_APPLICATION_ID": values["DISCORD_APPLICATION_ID"],
            "DISCORD_PUBLIC_KEY": values["DISCORD_PUBLIC_KEY"],
            "DISCORD_BOT_TOKEN": values["DISCORD_BOT_TOKEN"],
        }
    if medium is ChatMedium.EMAIL:
        return {
            "MAILGUN_API_KEY": values["MAILGUN_API_KEY"],
            "MAILGUN_DOMAIN": values["MAILGUN_DOMAIN"],
            "MAILGUN_FROM_EMAIL": values["MAILGUN_FROM_EMAIL"],
            "MAILGUN_WEBHOOK_SIGNING_KEY": values["MAILGUN_WEBHOOK_SIGNING_KEY"],
        }
    return {
        "SINCH_SERVICE_PLAN_ID": values["SINCH_SERVICE_PLAN_ID"],
        "SINCH_API_TOKEN": values["SINCH_API_TOKEN"],
        "SINCH_FROM_NUMBER": values["SINCH_FROM_NUMBER"],
        "SINCH_WEBHOOK_TOKEN": values["SINCH_WEBHOOK_TOKEN"],
    }


def _validate_required_values(values: Mapping[str, str], answers: SetupAnswers) -> None:
    required_keys = [
        "ADMIN_API_KEY",
        "OAUTH_BASE_URL",
        "YAHOO_CLIENT_ID",
        "YAHOO_CLIENT_SECRET",
        *(_llm_required_keys(answers.llm_provider)),
        *(_medium_required_keys(answers.chat_media)),
        *(_billing_required_keys(answers.hosted)),
    ]
    missing = [key for key in required_keys if not values.get(key, "").strip()]
    if missing:
        missing_list = ", ".join(missing)
        raise SetupInputError(f"Missing required setup values: {missing_list}.")


def _llm_required_keys(provider: LLMProvider) -> tuple[str, ...]:
    if provider is LLMProvider.OPENAI:
        return ("OPENAI_API_KEY",)
    return ("ANTHROPIC_API_KEY",)


def _medium_required_keys(media: Sequence[ChatMedium]) -> tuple[str, ...]:
    required: list[str] = []
    for medium in media:
        if medium is ChatMedium.TELEGRAM:
            required.append("TELEGRAM_BOT_TOKEN")
        elif medium is ChatMedium.DISCORD:
            required.extend(("DISCORD_APPLICATION_ID", "DISCORD_PUBLIC_KEY", "DISCORD_BOT_TOKEN"))
        elif medium is ChatMedium.EMAIL:
            required.extend(
                (
                    "MAILGUN_API_KEY",
                    "MAILGUN_DOMAIN",
                    "MAILGUN_FROM_EMAIL",
                    "MAILGUN_WEBHOOK_SIGNING_KEY",
                )
            )
        else:
            required.extend(
                (
                    "SINCH_SERVICE_PLAN_ID",
                    "SINCH_API_TOKEN",
                    "SINCH_FROM_NUMBER",
                    "SINCH_WEBHOOK_TOKEN",
                )
            )
    return tuple(required)


def _billing_required_keys(hosted: bool) -> tuple[str, ...]:
    if not hosted:
        return ()
    return (
        "CREEM_API_KEY",
        "CREEM_WEBHOOK_SECRET",
        "CREEM_PRODUCT_STANDARD_MONTHLY",
        "CREEM_PRODUCT_STANDARD_ANNUAL",
        "CREEM_PRODUCT_ALLSTAR_MONTHLY",
        "CREEM_PRODUCT_ALLSTAR_ANNUAL",
    )


def _default_llm_model(provider: LLMProvider) -> str:
    if provider is LLMProvider.OPENAI:
        return "gpt-4o-mini"
    return "claude-sonnet-4-5"


def _serialize_env_value(value: str) -> str:
    if value == "":
        return ""
    if re.search(r"\s|#|\"", value):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _validate_docker_available() -> None:
    if shutil.which("docker") is None:
        raise SetupInputError(
            "Docker was not found on PATH. Install Docker, then re-run `uv run gordie init`."
        )


if __name__ == "__main__":
    app()
