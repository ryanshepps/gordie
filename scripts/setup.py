"""Interactive setup wizard for self-hosting Gordie."""

from __future__ import annotations

import re
import secrets
import selectors
import shutil
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from ipaddress import ip_address
from pathlib import Path
from typing import Annotated, Final, cast
from urllib.parse import urlparse

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


class DiscordMode(StrEnum):
    GATEWAY = "gateway"
    INTERACTIONS = "interactions"


@dataclass(frozen=True, slots=True)
class SetupAnswers:
    deployment_target: DeploymentTarget
    chat_media: tuple[ChatMedium, ...]
    llm_provider: LLMProvider
    values: Mapping[str, str]
    hosted: bool


_ENV_ASSIGNMENT_RE = re.compile(r"^([A-Z][A-Z0-9_]*)=(.*?)(\s+#.*)?$")
_CHAT_MEDIUM_VALUES = ", ".join(medium.value for medium in ChatMedium)
_OPENAI_API_KEYS_URL: Final = "https://platform.openai.com/api-keys"
_ANTHROPIC_API_KEYS_URL: Final = "https://console.anthropic.com/settings/keys"
_YAHOO_APP_URL = "https://developer.yahoo.com/apps/"
_TELEGRAM_BOTFATHER_URL: Final = "https://t.me/BotFather"
_DISCORD_APPLICATIONS_URL = "https://discord.com/developers/applications"
_DISCORD_USER_ID_HELP_URL = "https://support.discord.com/hc/en-us/articles/206346498-Where-can-I-find-my-User-Server-Message-ID"
_MAILGUN_API_SECURITY_URL: Final = "https://app.mailgun.com/app/account/security/api_keys"
_MAILGUN_DOMAINS_URL: Final = "https://app.mailgun.com/mg/sending/domains"
_SINCH_SMS_SERVICE_APIS_URL: Final = "https://dashboard.sinch.com/sms/api/services"
_SINCH_NUMBERS_URL: Final = "https://dashboard.sinch.com/numbers/your-numbers"
_CREEM_DASHBOARD_URL: Final = "https://www.creem.io/dashboard"
_CREEM_PRODUCTS_URL: Final = "https://www.creem.io/dashboard/products"
_DEFAULT_CHAT_MEDIUM: Final = ChatMedium.DISCORD
_DEFAULT_ENV_FILE: Final = Path(".env")
_DEFAULT_TEMPLATE_FILE: Final = Path(".env.example")
_NGROK_AUTHTOKEN_URL: Final = "https://dashboard.ngrok.com/get-started/your-authtoken"
_NGROK_TUNNEL_SERVICE: Final = "http://server:8000"
_NGROK_DISCOVERY_SERVICE: Final = "http://localhost:8000"
_NGROK_DISCOVERY_TIMEOUT_SECONDS: Final = 20.0
_NGROK_PUBLIC_URL_RE = re.compile(r"https://[A-Za-z0-9.-]+\.ngrok(?:-free)?\.(?:app|dev|pizza|io)")


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

    values: dict[str, str] = {
        "DATABASE_URL": answers.values.get(
            "DATABASE_URL",
            "postgresql://postgres:postgres@postgres:5432/fantasy_agent",
        ),
        "ADMIN_API_KEY": admin_api_key or secrets.token_hex(32),
        "ENVIRONMENT": answers.values.get("ENVIRONMENT", "development"),
        "OAUTH_BASE_URL": answers.values["OAUTH_BASE_URL"],
        "NGROK_AUTHTOKEN": answers.values.get("NGROK_AUTHTOKEN", ""),
        "CHAT_MEDIA": ",".join(medium.value for medium in answers.chat_media),
        "LLM_PROVIDER": answers.llm_provider.value,
        "LLM_MODEL": answers.values.get("LLM_MODEL", _default_llm_model(answers.llm_provider)),
        "OPENAI_API_KEY": answers.values.get("OPENAI_API_KEY", ""),
        "ANTHROPIC_API_KEY": answers.values.get("ANTHROPIC_API_KEY", ""),
        "YAHOO_CLIENT_ID": answers.values["YAHOO_CLIENT_ID"],
        "YAHOO_CLIENT_SECRET": answers.values["YAHOO_CLIENT_SECRET"],
        "ENABLED_SPORTS": answers.values.get("ENABLED_SPORTS", "nhl,mlb"),
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
                "CREEM_API_KEY": answers.values.get("CREEM_API_KEY", ""),
                "CREEM_WEBHOOK_SECRET": answers.values.get("CREEM_WEBHOOK_SECRET", ""),
                "CREEM_API_BASE_URL": answers.values.get(
                    "CREEM_API_BASE_URL",
                    "https://test-api.creem.io/v1",
                ),
                "CREEM_PRODUCT_STANDARD_MONTHLY": answers.values.get(
                    "CREEM_PRODUCT_STANDARD_MONTHLY",
                    "",
                ),
                "CREEM_PRODUCT_STANDARD_ANNUAL": answers.values.get(
                    "CREEM_PRODUCT_STANDARD_ANNUAL",
                    "",
                ),
                "CREEM_PRODUCT_ALLSTAR_MONTHLY": answers.values.get(
                    "CREEM_PRODUCT_ALLSTAR_MONTHLY",
                    "",
                ),
                "CREEM_PRODUCT_ALLSTAR_ANNUAL": answers.values.get(
                    "CREEM_PRODUCT_ALLSTAR_ANNUAL",
                    "",
                ),
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
        typer.Option("--force", help="Ignore existing dotenv values and overwrite."),
    ] = False,
    skip_docker_check: Annotated[
        bool,
        typer.Option("--skip-docker-check", help="Skip Docker detection.", hidden=True),
    ] = False,
    skip_docker_start: Annotated[
        bool,
        typer.Option("--skip-docker-start", help="Skip docker compose startup.", hidden=True),
    ] = False,
    skip_ngrok_automation: Annotated[
        bool,
        typer.Option(
            "--skip-ngrok-automation",
            help="Skip ngrok install and dev-domain discovery prompts.",
            hidden=True,
        ),
    ] = False,
) -> None:
    """Create a local .env file through an interactive setup wizard."""

    try:
        if not template_file.exists():
            raise SetupInputError(f"{template_file} does not exist.")

        existing_values = (
            parse_env_values(env_file.read_text()) if env_file.exists() and not force else {}
        )
        if existing_values:
            typer.echo(f"Using existing values from {env_file}")

        answers = _prompt_for_answers(
            hosted=hosted,
            skip_docker_check=skip_docker_check,
            skip_ngrok_automation=skip_ngrok_automation,
            existing_values=existing_values,
        )
        generated_values = build_env_values(
            answers,
            admin_api_key=_existing_value(existing_values, "ADMIN_API_KEY"),
        )
        env_text = render_env_file(template_file.read_text(), existing_values | generated_values)
        _ = env_file.write_text(env_text)
        typer.secho(f"Wrote {env_file}", fg=typer.colors.GREEN)
        if answers.deployment_target is DeploymentTarget.DOCKER:
            _start_docker_compose(skip_docker_start=skip_docker_start)
    except SetupInputError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    _print_next_steps(answers)


def parse_env_values(env_text: str) -> dict[str, str]:
    """Parse dotenv assignments generated or accepted by the setup wizard."""

    values: dict[str, str] = {}
    for line in env_text.splitlines():
        match = _ENV_ASSIGNMENT_RE.match(line)
        if match is None:
            continue

        key, raw_value, _comment = match.groups()
        values[key] = _deserialize_env_value(raw_value.strip())

    return values


def _prompt_for_answers(
    *,
    hosted: bool,
    skip_docker_check: bool,
    skip_ngrok_automation: bool,
    existing_values: Mapping[str, str],
) -> SetupAnswers:
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
    chat_media = _prompt_chat_media(existing_value=_existing_value(existing_values, "CHAT_MEDIA"))

    values: dict[str, str] = {}
    for medium in chat_media:
        values.update(_prompt_medium_values(medium, existing_values, hosted=hosted))

    llm_provider = _prompt_enum(
        "LLM provider",
        LLMProvider,
        default=LLMProvider.OPENAI,
        existing_value=_existing_value(existing_values, "LLM_PROVIDER"),
    )
    values.update(_prompt_llm_values(llm_provider, existing_values))

    values.update(
        _prompt_ngrok_tunnel_values(
            existing_values,
            skip_automation=skip_ngrok_automation,
        )
    )

    typer.echo("")
    typer.echo(f"Create a Yahoo app at {_YAHOO_APP_URL}")
    typer.echo("Use this callback URL when Yahoo asks for a redirect URI:")
    typer.echo(f"  {values['OAUTH_BASE_URL'].rstrip('/')}/callback")
    values["YAHOO_CLIENT_ID"] = _existing_or_prompt_required(
        "YAHOO_CLIENT_ID",
        "Yahoo client ID",
        existing_values,
        help_url=_YAHOO_APP_URL,
        help_label="Yahoo developer apps",
    )
    values["YAHOO_CLIENT_SECRET"] = _existing_or_prompt_required(
        "YAHOO_CLIENT_SECRET",
        "Yahoo client secret",
        existing_values,
        hide_input=True,
        help_url=_YAHOO_APP_URL,
        help_label="Yahoo developer apps",
    )

    if hosted:
        values.update(_prompt_billing_values(existing_values))

    return SetupAnswers(
        deployment_target=deployment_target,
        chat_media=chat_media,
        llm_provider=llm_provider,
        values=dict(existing_values) | values,
        hosted=hosted,
    )


def _prompt_chat_media(*, existing_value: str | None = None) -> tuple[ChatMedium, ...]:
    if existing_value is not None:
        try:
            typer.echo("Chat media: using existing value")
            return parse_chat_media(existing_value)
        except SetupInputError as exc:
            typer.secho(str(exc), fg=typer.colors.RED)

    while True:
        raw_value = _prompt_text("Chat media", default=_DEFAULT_CHAT_MEDIUM.value)
        try:
            return parse_chat_media(raw_value)
        except SetupInputError as exc:
            typer.secho(str(exc), fg=typer.colors.RED)


def _prompt_llm_values(
    provider: LLMProvider,
    existing_values: Mapping[str, str],
) -> dict[str, str]:
    if provider is LLMProvider.OPENAI:
        return {
            "OPENAI_API_KEY": _existing_or_prompt_required(
                "OPENAI_API_KEY",
                "OpenAI API key",
                existing_values,
                hide_input=True,
                help_url=_OPENAI_API_KEYS_URL,
                help_label="OpenAI API keys",
            )
        }

    return {
        "ANTHROPIC_API_KEY": _existing_or_prompt_required(
            "ANTHROPIC_API_KEY",
            "Anthropic API key",
            existing_values,
            hide_input=True,
            help_url=_ANTHROPIC_API_KEYS_URL,
            help_label="Anthropic API keys",
        )
    }


def _prompt_ngrok_tunnel_values(
    existing_values: Mapping[str, str],
    *,
    skip_automation: bool,
) -> dict[str, str]:
    typer.echo("")
    typer.echo("ngrok tunnel setup")

    existing_oauth_base_url = _existing_value(existing_values, "OAUTH_BASE_URL")
    existing_authtoken = _existing_value(existing_values, "NGROK_AUTHTOKEN")
    if existing_oauth_base_url is not None and existing_authtoken is not None:
        return {
            "OAUTH_BASE_URL": _prompt_https_oauth_base_url(existing_values),
            "NGROK_AUTHTOKEN": _prompt_ngrok_authtoken(existing_values),
        }

    if not skip_automation:
        automated_values = _prompt_ngrok_tunnel_automation(existing_values)
        if automated_values is not None:
            return automated_values

    typer.echo(f"The Docker connector sends tunnel traffic to: {_NGROK_TUNNEL_SERVICE}")

    return {
        "OAUTH_BASE_URL": _prompt_https_oauth_base_url(existing_values),
        "NGROK_AUTHTOKEN": _prompt_ngrok_authtoken(existing_values),
    }


def _prompt_ngrok_tunnel_automation(
    existing_values: Mapping[str, str],
) -> dict[str, str] | None:
    ngrok_path = _ensure_ngrok_available()
    if ngrok_path is None:
        return None

    if not typer.confirm(
        "Configure ngrok and use your account's dev domain?",
        default=True,
    ):
        typer.echo("Skipping ngrok automation.")
        return None

    authtoken = _prompt_ngrok_authtoken(existing_values)
    if not _configure_ngrok_authtoken(ngrok_path, authtoken):
        return None

    oauth_base_url = _discover_ngrok_oauth_base_url(ngrok_path)
    if oauth_base_url is None:
        typer.secho(
            "Could not detect your ngrok dev domain. Falling back to manual URL entry.",
            fg=typer.colors.YELLOW,
        )
        return {
            "OAUTH_BASE_URL": _prompt_https_oauth_base_url(existing_values),
            "NGROK_AUTHTOKEN": authtoken,
        }

    typer.secho("ngrok tunnel configured.", fg=typer.colors.GREEN)
    return {
        "OAUTH_BASE_URL": oauth_base_url,
        "NGROK_AUTHTOKEN": authtoken,
    }


def _prompt_ngrok_authtoken(existing_values: Mapping[str, str]) -> str:
    if _existing_value(existing_values, "NGROK_AUTHTOKEN") is None:
        typer.echo(f"Find your ngrok authtoken here: {_NGROK_AUTHTOKEN_URL}")

    return _existing_or_prompt_required(
        "NGROK_AUTHTOKEN",
        "ngrok authtoken",
        existing_values,
        hide_input=True,
    )


def _ensure_ngrok_available() -> str | None:
    ngrok_path = shutil.which("ngrok")
    if ngrok_path is not None:
        typer.echo("ngrok: found on PATH")
        return ngrok_path

    typer.secho("ngrok was not found on PATH.", fg=typer.colors.YELLOW)
    if not typer.confirm("Install ngrok now?", default=True):
        typer.echo("Skipping ngrok automation.")
        return None

    if not _install_ngrok():
        return None

    ngrok_path = shutil.which("ngrok")
    if ngrok_path is None:
        typer.secho(
            "ngrok installation finished, but ngrok is still not on PATH.",
            fg=typer.colors.RED,
        )
        return None
    return ngrok_path


def _install_ngrok() -> bool:
    brew_path = shutil.which("brew")
    if brew_path is None:
        typer.secho(
            "Automatic ngrok install currently needs Homebrew. Falling back to manual setup.",
            fg=typer.colors.YELLOW,
        )
        return False

    try:
        _ = _run_setup_command([brew_path, "install", "ngrok"])
    except SetupInputError as exc:
        typer.secho(f"ngrok install failed: {exc}", fg=typer.colors.RED)
        return False

    return True


def _configure_ngrok_authtoken(ngrok_path: str, authtoken: str) -> bool:
    try:
        _ = _run_setup_command([ngrok_path, "config", "add-authtoken", authtoken])
    except SetupInputError as exc:
        typer.secho(f"ngrok auth setup failed: {exc}", fg=typer.colors.RED)
        return False

    return True


def _discover_ngrok_oauth_base_url(ngrok_path: str) -> str | None:
    typer.echo("Starting ngrok briefly to detect your assigned dev domain...")
    process = subprocess.Popen(
        [
            ngrok_path,
            "http",
            _NGROK_DISCOVERY_SERVICE,
            "--log",
            "stdout",
            "--log-format",
            "json",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        return _read_ngrok_public_url(process)
    finally:
        _stop_process(process)


def _read_ngrok_public_url(process: subprocess.Popen[str]) -> str | None:
    stdout = process.stdout
    if stdout is None:
        return None

    selector = selectors.DefaultSelector()
    _ = selector.register(stdout, selectors.EVENT_READ)
    deadline = time.monotonic() + _NGROK_DISCOVERY_TIMEOUT_SECONDS
    try:
        while time.monotonic() < deadline:
            timeout = max(0.0, deadline - time.monotonic())
            events = selector.select(timeout=timeout)
            if not events:
                return None

            line = stdout.readline()
            public_url_match = _NGROK_PUBLIC_URL_RE.search(line)
            if public_url_match is not None:
                return _normalize_https_base_url(public_url_match.group(0))
            if process.poll() is not None:
                return None
    finally:
        _ = selector.unregister(stdout)
        selector.close()

    return None


def _stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return

    process.terminate()
    try:
        _ = process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        _ = process.wait(timeout=5)


def _run_setup_command(
    command: Sequence[str],
    *,
    capture_output: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            list(command),
            check=check,
            capture_output=capture_output,
            text=True,
        )
    except FileNotFoundError as exc:
        raise SetupInputError(f"{command[0]} was not found.") from exc
    except subprocess.CalledProcessError as exc:
        command_text = " ".join(command)
        raise SetupInputError(f"`{command_text}` failed with exit code {exc.returncode}.") from exc

    return completed


def _prompt_https_oauth_base_url(existing_values: Mapping[str, str]) -> str:
    existing_value = _existing_value(existing_values, "OAUTH_BASE_URL")
    if existing_value is not None:
        try:
            normalized = _normalize_https_base_url(existing_value)
            typer.echo("OAuth base URL: using existing value")
            return normalized
        except SetupInputError as exc:
            typer.secho(f"Existing OAUTH_BASE_URL is invalid: {exc}", fg=typer.colors.RED)

    while True:
        raw_value = _prompt_required("ngrok public HTTPS URL")
        try:
            return _normalize_https_base_url(raw_value)
        except SetupInputError as exc:
            typer.secho(str(exc), fg=typer.colors.RED)


def _prompt_medium_values(
    medium: ChatMedium,
    existing_values: Mapping[str, str],
    *,
    hosted: bool,
) -> dict[str, str]:
    typer.echo("")
    if medium is ChatMedium.TELEGRAM:
        typer.echo("Telegram setup")
        return {
            "TELEGRAM_BOT_TOKEN": _existing_or_prompt_required(
                "TELEGRAM_BOT_TOKEN",
                "Telegram bot token",
                existing_values,
                hide_input=True,
                help_url=_TELEGRAM_BOTFATHER_URL,
                help_label="Create or manage your Telegram bot with BotFather",
            )
        }

    if medium is ChatMedium.DISCORD:
        mode = _discord_mode_for_setup(hosted=hosted)
        application_id = _existing_or_prompt_required(
            "DISCORD_APPLICATION_ID",
            "Discord application ID",
            existing_values,
            help_url=f"{_DISCORD_APPLICATIONS_URL} (General Information)",
            help_label="Discord application",
        )
        if mode is DiscordMode.GATEWAY:
            bot_token = _existing_or_prompt_required(
                "DISCORD_BOT_TOKEN",
                "Discord bot token",
                existing_values,
                hide_input=True,
                help_url=_discord_bot_url(application_id),
                help_label="Discord bot token",
            )
            allowed_user_ids = _existing_or_prompt_required(
                "DISCORD_ALLOWED_USER_IDS",
                "Discord allowed user IDs",
                existing_values,
                help_url=_DISCORD_USER_ID_HELP_URL,
                help_label="Discord user ID help",
            )
            typer.echo(f"Message Content Intent: {_discord_bot_url(application_id)}")
            typer.echo("Enable Message Content Intent for Gateway mode.")
            return {
                "DISCORD_MODE": mode.value,
                "DISCORD_APPLICATION_ID": application_id,
                "DISCORD_BOT_TOKEN": bot_token,
                "DISCORD_ALLOWED_USER_IDS": allowed_user_ids,
                "DISCORD_REQUIRE_MENTION": _existing_or_prompt_text(
                    "DISCORD_REQUIRE_MENTION",
                    "Require @mention in servers",
                    existing_values,
                    default="true",
                ),
            }

        public_key = _existing_or_prompt_required(
            "DISCORD_PUBLIC_KEY",
            "Discord public key",
            existing_values,
            hide_input=True,
            help_url=f"{_DISCORD_APPLICATIONS_URL} (General Information)",
            help_label="Discord public key",
        )
        return {
            "DISCORD_MODE": mode.value,
            "DISCORD_APPLICATION_ID": application_id,
            "DISCORD_PUBLIC_KEY": public_key,
        }

    if medium is ChatMedium.EMAIL:
        typer.echo("Email setup (Mailgun)")
        domain = _existing_or_prompt_required(
            "MAILGUN_DOMAIN",
            "Mailgun domain",
            existing_values,
            help_url=_MAILGUN_DOMAINS_URL,
            help_label="Mailgun sending domains",
        )
        return {
            "MAILGUN_API_KEY": _existing_or_prompt_required(
                "MAILGUN_API_KEY",
                "Mailgun API key",
                existing_values,
                hide_input=True,
                help_url=_MAILGUN_API_SECURITY_URL,
                help_label="Mailgun API keys",
            ),
            "MAILGUN_DOMAIN": domain,
            "MAILGUN_FROM_EMAIL": _existing_or_prompt_text(
                "MAILGUN_FROM_EMAIL",
                "Mailgun from email",
                existing_values,
                default=f"Gordie <gordie@{domain}>",
            ),
            "MAILGUN_WEBHOOK_SIGNING_KEY": _existing_or_prompt_required(
                "MAILGUN_WEBHOOK_SIGNING_KEY",
                "Mailgun webhook signing key",
                existing_values,
                hide_input=True,
                help_url=_MAILGUN_API_SECURITY_URL,
                help_label="Mailgun HTTP webhook signing key",
            ),
        }

    typer.echo("SMS setup (Sinch)")
    return {
        "SINCH_SERVICE_PLAN_ID": _existing_or_prompt_required(
            "SINCH_SERVICE_PLAN_ID",
            "Sinch service plan ID",
            existing_values,
            help_url=_SINCH_SMS_SERVICE_APIS_URL,
            help_label="Sinch SMS Service APIs",
        ),
        "SINCH_API_TOKEN": _existing_or_prompt_required(
            "SINCH_API_TOKEN",
            "Sinch API token",
            existing_values,
            hide_input=True,
            help_url=_SINCH_SMS_SERVICE_APIS_URL,
            help_label="Sinch SMS Service APIs",
        ),
        "SINCH_FROM_NUMBER": _existing_or_prompt_required(
            "SINCH_FROM_NUMBER",
            "Sinch from number",
            existing_values,
            help_url=_SINCH_NUMBERS_URL,
            help_label="Sinch numbers",
        ),
        "SINCH_WEBHOOK_TOKEN": _existing_or_prompt_required(
            "SINCH_WEBHOOK_TOKEN",
            "Sinch webhook token",
            existing_values,
            hide_input=True,
            help_url=_SINCH_SMS_SERVICE_APIS_URL,
            help_label="Set this webhook token in Sinch SMS callbacks",
        ),
    }


def _prompt_billing_values(existing_values: Mapping[str, str]) -> dict[str, str]:
    typer.echo("")
    typer.echo("Hosted billing setup (Creem)")
    return {
        "CREEM_API_KEY": _existing_or_prompt_required(
            "CREEM_API_KEY",
            "Creem API key",
            existing_values,
            hide_input=True,
            help_url=_CREEM_DASHBOARD_URL,
            help_label="Creem dashboard API keys",
        ),
        "CREEM_WEBHOOK_SECRET": _existing_or_prompt_required(
            "CREEM_WEBHOOK_SECRET",
            "Creem webhook secret",
            existing_values,
            hide_input=True,
            help_url=_CREEM_DASHBOARD_URL,
            help_label="Creem dashboard webhooks",
        ),
        "CREEM_API_BASE_URL": _existing_or_prompt_text(
            "CREEM_API_BASE_URL",
            "Creem API base URL",
            existing_values,
            default="https://test-api.creem.io/v1",
        ),
        "CREEM_PRODUCT_STANDARD_MONTHLY": _existing_or_prompt_required(
            "CREEM_PRODUCT_STANDARD_MONTHLY",
            "Creem standard monthly product ID",
            existing_values,
            help_url=_CREEM_PRODUCTS_URL,
            help_label="Creem products",
        ),
        "CREEM_PRODUCT_STANDARD_ANNUAL": _existing_or_prompt_required(
            "CREEM_PRODUCT_STANDARD_ANNUAL",
            "Creem standard annual product ID",
            existing_values,
            help_url=_CREEM_PRODUCTS_URL,
            help_label="Creem products",
        ),
        "CREEM_PRODUCT_ALLSTAR_MONTHLY": _existing_or_prompt_required(
            "CREEM_PRODUCT_ALLSTAR_MONTHLY",
            "Creem all-star monthly product ID",
            existing_values,
            help_url=_CREEM_PRODUCTS_URL,
            help_label="Creem products",
        ),
        "CREEM_PRODUCT_ALLSTAR_ANNUAL": _existing_or_prompt_required(
            "CREEM_PRODUCT_ALLSTAR_ANNUAL",
            "Creem all-star annual product ID",
            existing_values,
            help_url=_CREEM_PRODUCTS_URL,
            help_label="Creem products",
        ),
    }


def _prompt_enum[T: StrEnum](
    label: str,
    enum_type: type[T],
    *,
    default: T,
    existing_value: str | None = None,
) -> T:
    if existing_value is not None:
        try:
            typer.echo(f"{label}: using existing value")
            return enum_type(existing_value.strip().lower())
        except ValueError:
            typer.secho(f"Existing {label.lower()} is invalid.", fg=typer.colors.RED)

    choices = ", ".join(item.value for item in enum_type)
    while True:
        raw_value = _prompt_text(f"{label} ({choices})", default=default.value)
        normalized = raw_value.strip().lower()
        try:
            return enum_type(normalized)
        except ValueError:
            typer.secho(f"Choose one of: {choices}.", fg=typer.colors.RED)


def _discord_mode_for_setup(*, hosted: bool) -> DiscordMode:
    if hosted:
        typer.echo("Discord mode: interactions (hosted)")
        return DiscordMode.INTERACTIONS

    typer.echo("Discord mode: gateway")
    return DiscordMode.GATEWAY


def _existing_or_prompt_required(
    key: str,
    label: str,
    existing_values: Mapping[str, str],
    *,
    hide_input: bool = False,
    help_url: str | None = None,
    help_label: str | None = None,
) -> str:
    existing_value = _existing_value(existing_values, key)
    if existing_value is not None:
        typer.echo(f"{label}: using existing value")
        return existing_value

    if help_url is not None:
        typer.echo(f"{help_label or label}: {help_url}")

    return _prompt_required(label, hide_input=hide_input)


def _prompt_required(label: str, *, hide_input: bool = False) -> str:
    while True:
        value = _prompt_text(label, hide_input=hide_input).strip()
        if value:
            return value
        typer.secho(f"{label} is required.", fg=typer.colors.RED)


def _existing_or_prompt_text(
    key: str,
    label: str,
    existing_values: Mapping[str, str],
    *,
    default: str,
    hide_input: bool = False,
) -> str:
    existing_value = _existing_value(existing_values, key)
    if existing_value is not None:
        typer.echo(f"{label}: using existing value")
        return existing_value

    return _prompt_text(label, default=default, hide_input=hide_input)


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


def _discord_bot_url(application_id: str) -> str:
    return f"{_DISCORD_APPLICATIONS_URL}/{application_id}/bot"


def _discord_invite_url(application_id: str) -> str:
    return (
        "https://discord.com/oauth2/authorize"
        f"?client_id={application_id}&scope=bot&permissions=68608"
    )


def _start_docker_compose(*, skip_docker_start: bool) -> None:
    if skip_docker_start:
        return

    typer.echo("")
    typer.echo("Starting Docker services...")
    try:
        _ = subprocess.run(["docker", "compose", "up", "-d", "--build"], check=True)
    except FileNotFoundError as exc:
        raise SetupInputError("Docker Compose was not found.") from exc
    except subprocess.CalledProcessError as exc:
        raise SetupInputError(
            f"docker compose up -d --build failed with exit code {exc.returncode}."
        ) from exc


def _print_next_steps(answers: SetupAnswers) -> None:
    typer.echo("")
    typer.echo("Next steps:")
    typer.echo("  Server health: http://localhost:8000/health")
    oauth_base_url = answers.values["OAUTH_BASE_URL"].rstrip("/")
    typer.echo(f"  Public health: {oauth_base_url}/health")
    typer.echo(f"  Yahoo redirect URI: {oauth_base_url}/callback")

    if ChatMedium.DISCORD not in answers.chat_media:
        return

    application_id = answers.values.get("DISCORD_APPLICATION_ID", "")
    discord_mode = answers.values.get("DISCORD_MODE", DiscordMode.GATEWAY.value)
    if discord_mode == DiscordMode.GATEWAY.value:
        typer.echo("")
        typer.echo("Discord Gateway:")
        typer.echo(f"  1. Enable Message Content Intent: {_discord_bot_url(application_id)}")
        typer.echo(f"  2. Invite the bot to your server: {_discord_invite_url(application_id)}")
        typer.echo("  3. DM the bot, or mention it in a server channel:")
        typer.echo("     @Gordie Who should I start tonight?")
        return

    typer.echo("")
    typer.echo("Discord Interactions:")
    typer.echo("  1. Set this Interactions Endpoint URL in the Discord Developer Portal:")
    typer.echo(f"     {oauth_base_url}/discord/interactions")
    typer.echo("  2. Use the /gordie command after Discord verifies the endpoint.")


def _existing_value(values: Mapping[str, str], key: str) -> str | None:
    value = values.get(key)
    if value is None or not value.strip():
        return None
    return value


def _medium_env_values(medium: ChatMedium, values: Mapping[str, str]) -> dict[str, str]:
    if medium is ChatMedium.TELEGRAM:
        return {"TELEGRAM_BOT_TOKEN": values["TELEGRAM_BOT_TOKEN"]}
    if medium is ChatMedium.DISCORD:
        discord_mode = values.get("DISCORD_MODE", DiscordMode.GATEWAY.value)
        return {
            "DISCORD_MODE": discord_mode,
            "DISCORD_APPLICATION_ID": values["DISCORD_APPLICATION_ID"],
            "DISCORD_PUBLIC_KEY": values.get("DISCORD_PUBLIC_KEY", ""),
            "DISCORD_BOT_TOKEN": values.get("DISCORD_BOT_TOKEN", ""),
            "DISCORD_ALLOWED_USER_IDS": values.get("DISCORD_ALLOWED_USER_IDS", ""),
            "DISCORD_REQUIRE_MENTION": values.get("DISCORD_REQUIRE_MENTION", "true"),
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
        "NGROK_AUTHTOKEN",
        "YAHOO_CLIENT_ID",
        "YAHOO_CLIENT_SECRET",
        *(_llm_required_keys(answers.llm_provider)),
        *(_medium_required_keys(answers.chat_media, values)),
        *(_billing_required_keys(answers.hosted)),
    ]
    missing = [key for key in required_keys if not values.get(key, "").strip()]
    if missing:
        missing_list = ", ".join(missing)
        raise SetupInputError(f"Missing required setup values: {missing_list}.")

    _ = _normalize_https_base_url(values["OAUTH_BASE_URL"])


def _llm_required_keys(provider: LLMProvider) -> tuple[str, ...]:
    if provider is LLMProvider.OPENAI:
        return ("OPENAI_API_KEY",)
    return ("ANTHROPIC_API_KEY",)


def _medium_required_keys(
    media: Sequence[ChatMedium],
    values: Mapping[str, str],
) -> tuple[str, ...]:
    required: list[str] = []
    for medium in media:
        if medium is ChatMedium.TELEGRAM:
            required.append("TELEGRAM_BOT_TOKEN")
        elif medium is ChatMedium.DISCORD:
            required.extend(_discord_required_keys(values))
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


def _discord_required_keys(values: Mapping[str, str]) -> tuple[str, ...]:
    mode = values.get("DISCORD_MODE", DiscordMode.GATEWAY.value).strip().lower()
    if mode == DiscordMode.INTERACTIONS.value:
        return ("DISCORD_MODE", "DISCORD_APPLICATION_ID", "DISCORD_PUBLIC_KEY")
    return (
        "DISCORD_MODE",
        "DISCORD_APPLICATION_ID",
        "DISCORD_BOT_TOKEN",
        "DISCORD_ALLOWED_USER_IDS",
    )


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


def _normalize_https_base_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme != "https" or not parsed.netloc:
        raise SetupInputError(
            "OAUTH_BASE_URL must be a public HTTPS URL, for example https://gordie.example.com."
        )
    hostname = parsed.hostname
    if hostname is None or _is_private_hostname(hostname):
        raise SetupInputError(
            "OAUTH_BASE_URL must be a public HTTPS URL, for example https://gordie.example.com."
        )
    if parsed.path not in ("", "/") or parsed.params or parsed.query or parsed.fragment:
        raise SetupInputError("OAUTH_BASE_URL must not include a path, query string, or fragment.")
    return normalized


def _is_private_hostname(hostname: str) -> bool:
    normalized = hostname.strip().lower().rstrip(".")
    if normalized in {"localhost"} or normalized.endswith(".localhost"):
        return True

    try:
        parsed_ip = ip_address(normalized)
    except ValueError:
        return False

    return not parsed_ip.is_global


def _serialize_env_value(value: str) -> str:
    if value == "":
        return ""
    if re.search(r"\s|#|\"", value):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _deserialize_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return _unescape_double_quoted_value(value[1:-1])
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1]
    return value


def _unescape_double_quoted_value(value: str) -> str:
    unescaped: list[str] = []
    escaped = False
    for char in value:
        if escaped:
            unescaped.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        else:
            unescaped.append(char)

    if escaped:
        unescaped.append("\\")

    return "".join(unescaped)


def _validate_docker_available() -> None:
    if shutil.which("docker") is None:
        raise SetupInputError(
            "Docker was not found on PATH. Install Docker, then re-run `uv run gordie init`."
        )


if __name__ == "__main__":
    app()
