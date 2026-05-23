"""Tests for the Gordie setup CLI."""

from pathlib import Path

import pytest
from pytest import MonkeyPatch
from typer.testing import CliRunner

from scripts.setup import (
    ChatMedium,
    DeploymentTarget,
    LLMProvider,
    SetupAnswers,
    SetupInputError,
    app,
    build_env_values,
    parse_chat_media,
    parse_env_values,
    render_env_file,
)


def test_parse_chat_media_requires_at_least_one_medium() -> None:
    with pytest.raises(SetupInputError, match="at least one"):
        _ = parse_chat_media(" ")


def test_parse_chat_media_rejects_unknown_medium() -> None:
    with pytest.raises(SetupInputError, match="slack"):
        _ = parse_chat_media("telegram, slack")


def test_build_env_values_skips_billing_by_default() -> None:
    answers = SetupAnswers(
        deployment_target=DeploymentTarget.DOCKER,
        chat_media=(ChatMedium.TELEGRAM,),
        llm_provider=LLMProvider.OPENAI,
        hosted=False,
        values={
            "OAUTH_BASE_URL": "http://localhost:8000",
            "OPENAI_API_KEY": "sk-test",
            "YAHOO_CLIENT_ID": "yahoo-id",
            "YAHOO_CLIENT_SECRET": "yahoo-secret",
            "TELEGRAM_BOT_TOKEN": "telegram-token",
        },
    )

    values = build_env_values(answers, admin_api_key="admin-token")

    assert values["OPENAI_API_KEY"] == "sk-test"
    assert values["TELEGRAM_BOT_TOKEN"] == "telegram-token"
    assert values["CREEM_API_KEY"] == ""
    assert values["CREEM_WEBHOOK_SECRET"] == ""


def test_build_env_values_rejects_missing_required_keys() -> None:
    answers = SetupAnswers(
        deployment_target=DeploymentTarget.DOCKER,
        chat_media=(ChatMedium.SMS,),
        llm_provider=LLMProvider.ANTHROPIC,
        hosted=False,
        values={
            "OAUTH_BASE_URL": "http://localhost:8000",
            "ANTHROPIC_API_KEY": "anthropic-key",
            "YAHOO_CLIENT_ID": "yahoo-id",
            "YAHOO_CLIENT_SECRET": "yahoo-secret",
            "SINCH_SERVICE_PLAN_ID": "sinch-plan",
            "SINCH_API_TOKEN": "",
            "SINCH_FROM_NUMBER": "+15551234567",
            "SINCH_WEBHOOK_TOKEN": "webhook-token",
        },
    )

    with pytest.raises(SetupInputError, match="SINCH_API_TOKEN"):
        _ = build_env_values(answers, admin_api_key="admin-token")


def test_build_env_values_supports_all_media_and_anthropic() -> None:
    answers = SetupAnswers(
        deployment_target=DeploymentTarget.DOCKER,
        chat_media=(ChatMedium.DISCORD, ChatMedium.EMAIL, ChatMedium.SMS),
        llm_provider=LLMProvider.ANTHROPIC,
        hosted=False,
        values={
            "OAUTH_BASE_URL": "http://localhost:8000",
            "ANTHROPIC_API_KEY": "anthropic-key",
            "YAHOO_CLIENT_ID": "yahoo-id",
            "YAHOO_CLIENT_SECRET": "yahoo-secret",
            "DISCORD_APPLICATION_ID": "discord-app",
            "DISCORD_PUBLIC_KEY": "discord-public",
            "DISCORD_BOT_TOKEN": "discord-token",
            "MAILGUN_API_KEY": "mailgun-key",
            "MAILGUN_DOMAIN": "example.com",
            "MAILGUN_FROM_EMAIL": "Gordie <gordie@example.com>",
            "MAILGUN_WEBHOOK_SIGNING_KEY": "mailgun-webhook",
            "SINCH_SERVICE_PLAN_ID": "sinch-plan",
            "SINCH_API_TOKEN": "sinch-token",
            "SINCH_FROM_NUMBER": "+15551234567",
            "SINCH_WEBHOOK_TOKEN": "sinch-webhook",
        },
    )

    values = build_env_values(answers, admin_api_key="admin-token")

    assert values["LLM_PROVIDER"] == "anthropic"
    assert values["ANTHROPIC_API_KEY"] == "anthropic-key"
    assert values["CHAT_MEDIA"] == "discord,email,sms"
    assert values["DISCORD_APPLICATION_ID"] == "discord-app"
    assert values["MAILGUN_DOMAIN"] == "example.com"
    assert values["SINCH_FROM_NUMBER"] == "+15551234567"


def test_render_env_file_preserves_comments_and_quotes_values() -> None:
    template = "\n".join(
        [
            "ADMIN_API_KEY=                          # openssl rand -hex 32",
            "MAILGUN_FROM_EMAIL=                     # e.g. sender",
            "OPENAI_API_KEY=",
        ]
    )

    rendered = render_env_file(
        template,
        {
            "ADMIN_API_KEY": "admin-token",
            "MAILGUN_FROM_EMAIL": "Gordie <gordie@example.com>",
            "OPENAI_API_KEY": "sk-test",
            "TELEGRAM_BOT_TOKEN": "telegram-token",
        },
    )

    assert "ADMIN_API_KEY=admin-token # openssl rand -hex 32" in rendered
    assert 'MAILGUN_FROM_EMAIL="Gordie <gordie@example.com>" # e.g. sender' in rendered
    assert "TELEGRAM_BOT_TOKEN=telegram-token" in rendered


def test_parse_env_values_unquotes_existing_values() -> None:
    values = parse_env_values(
        "\n".join(
            [
                "OPENAI_API_KEY=sk-test",
                'MAILGUN_FROM_EMAIL="Gordie <gordie@example.com>" # e.g. sender',
                "IGNORED LINE",
            ]
        )
    )

    assert values["OPENAI_API_KEY"] == "sk-test"
    assert values["MAILGUN_FROM_EMAIL"] == "Gordie <gordie@example.com>"


def test_init_command_writes_env_file(tmp_path: Path) -> None:
    template_file = tmp_path / ".env.example"
    env_file = tmp_path / ".env"
    _ = template_file.write_text(
        "\n".join(
            [
                "DATABASE_URL=",
                "ADMIN_API_KEY=",
                "ENVIRONMENT=",
                "OAUTH_BASE_URL=",
                "OPENAI_API_KEY=",
                "ANTHROPIC_API_KEY=",
                "LLM_PROVIDER=",
                "LLM_MODEL=",
                "YAHOO_CLIENT_ID=",
                "YAHOO_CLIENT_SECRET=",
                "CHAT_MEDIA=",
                "DISCORD_APPLICATION_ID=",
                "DISCORD_PUBLIC_KEY=",
                "DISCORD_BOT_TOKEN=",
                "CREEM_API_KEY=",
                "CREEM_WEBHOOK_SECRET=",
            ]
        )
    )
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "init",
            "--skip-docker-check",
            "--template-file",
            str(template_file),
            "--env-file",
            str(env_file),
        ],
        input="\n\n\n\nsk-test\nyahoo-id\nyahoo-secret\ndiscord-app\ndiscord-public\ndiscord-token\n",
    )

    assert result.exit_code == 0, result.output
    env_text = env_file.read_text()
    assert "CHAT_MEDIA=discord" in env_text
    assert "LLM_PROVIDER=openai" in env_text
    assert "OPENAI_API_KEY=sk-test" in env_text
    assert "YAHOO_CLIENT_ID=yahoo-id" in env_text
    assert "DISCORD_APPLICATION_ID=discord-app" in env_text
    assert "DISCORD_PUBLIC_KEY=discord-public" in env_text
    assert "DISCORD_BOT_TOKEN=discord-token" in env_text
    assert "Application ID: https://discord.com/developers/applications" in result.output
    assert "Public Key: https://discord.com/developers/applications" in result.output
    assert (
        "Bot Token: https://docs.discord.com/developers/quick-start/getting-started"
        in result.output
    )
    assert "CREEM_API_KEY=" in env_text
    assert "docker compose up -d" in result.output


def test_init_command_reuses_existing_env_values(tmp_path: Path) -> None:
    template_file = tmp_path / ".env.example"
    env_file = tmp_path / ".env"
    _ = template_file.write_text(
        "\n".join(
            [
                "DATABASE_URL=",
                "ADMIN_API_KEY=",
                "OAUTH_BASE_URL=",
                "OPENAI_API_KEY=",
                "ANTHROPIC_API_KEY=",
                "LLM_PROVIDER=",
                "LLM_MODEL=",
                "YAHOO_CLIENT_ID=",
                "YAHOO_CLIENT_SECRET=",
                "ENABLED_SPORTS=",
                "CHAT_MEDIA=",
                "TELEGRAM_BOT_TOKEN=",
                "CREEM_API_BASE_URL=",
            ]
        )
    )
    _ = env_file.write_text(
        "\n".join(
            [
                "DATABASE_URL=postgresql://existing",
                "ADMIN_API_KEY=existing-admin",
                "ENVIRONMENT=production",
                "OAUTH_BASE_URL=http://existing.example.com",
                "OPENAI_API_KEY=existing-openai",
                "LLM_PROVIDER=openai",
                "LLM_MODEL=existing-model",
                "YAHOO_CLIENT_ID=existing-yahoo-id",
                "YAHOO_CLIENT_SECRET=existing-yahoo-secret",
                "ENABLED_SPORTS=nhl",
                "CHAT_MEDIA=telegram",
                "TELEGRAM_BOT_TOKEN=existing-telegram",
                "CREEM_API_BASE_URL=https://existing-creem.example.com/v1",
                "",
            ]
        )
    )
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "init",
            "--skip-docker-check",
            "--template-file",
            str(template_file),
            "--env-file",
            str(env_file),
        ],
        input="\n",
    )

    assert result.exit_code == 0, result.output
    assert "Using existing values" in result.output
    assert "already exists" not in result.output
    env_text = env_file.read_text()
    assert "DATABASE_URL=postgresql://existing" in env_text
    assert "ADMIN_API_KEY=existing-admin" in env_text
    assert "ENVIRONMENT=production" in env_text
    assert "OAUTH_BASE_URL=http://existing.example.com" in env_text
    assert "OPENAI_API_KEY=existing-openai" in env_text
    assert "LLM_MODEL=existing-model" in env_text
    assert "YAHOO_CLIENT_SECRET=existing-yahoo-secret" in env_text
    assert "ENABLED_SPORTS=nhl" in env_text
    assert "TELEGRAM_BOT_TOKEN=existing-telegram" in env_text
    assert "CREEM_API_BASE_URL=https://existing-creem.example.com/v1" in env_text


def test_init_command_rejects_missing_template_file(tmp_path: Path) -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "init",
            "--skip-docker-check",
            "--template-file",
            str(tmp_path / "missing.env.example"),
            "--env-file",
            str(tmp_path / ".env"),
        ],
    )

    assert result.exit_code == 1
    assert "does not exist" in result.output


def test_init_command_requires_docker_by_default(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    template_file = tmp_path / ".env.example"
    _ = template_file.write_text("OPENAI_API_KEY=\n")

    def no_docker(_name: str) -> None:
        return None

    monkeypatch.setattr("scripts.setup.shutil.which", no_docker)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "init",
            "--template-file",
            str(template_file),
            "--env-file",
            str(tmp_path / ".env"),
        ],
        input="\n",
    )

    assert result.exit_code == 1
    assert "Docker was not found" in result.output


def test_init_command_reprompts_for_invalid_chat_media(tmp_path: Path) -> None:
    template_file = tmp_path / ".env.example"
    env_file = tmp_path / ".env"
    _ = template_file.write_text(
        "\n".join(
            [
                "DATABASE_URL=",
                "ADMIN_API_KEY=",
                "OAUTH_BASE_URL=",
                "OPENAI_API_KEY=",
                "LLM_PROVIDER=",
                "LLM_MODEL=",
                "YAHOO_CLIENT_ID=",
                "YAHOO_CLIENT_SECRET=",
                "CHAT_MEDIA=",
                "TELEGRAM_BOT_TOKEN=",
            ]
        )
    )
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "init",
            "--skip-docker-check",
            "--template-file",
            str(template_file),
            "--env-file",
            str(env_file),
        ],
        input="\nslack\ntelegram\n\n\nsk-test\nyahoo-id\nyahoo-secret\ntelegram-token\n",
    )

    assert result.exit_code == 0, result.output
    assert "Unknown chat medium: slack" in result.output
    assert "CHAT_MEDIA=telegram" in env_file.read_text()


def test_init_command_with_hosted_writes_billing_values(tmp_path: Path) -> None:
    template_file = tmp_path / ".env.example"
    env_file = tmp_path / ".env"
    _ = template_file.write_text(
        "\n".join(
            [
                "DATABASE_URL=",
                "ADMIN_API_KEY=",
                "OAUTH_BASE_URL=",
                "OPENAI_API_KEY=",
                "ANTHROPIC_API_KEY=",
                "LLM_PROVIDER=",
                "LLM_MODEL=",
                "YAHOO_CLIENT_ID=",
                "YAHOO_CLIENT_SECRET=",
                "CHAT_MEDIA=",
                "DISCORD_APPLICATION_ID=",
                "DISCORD_PUBLIC_KEY=",
                "DISCORD_BOT_TOKEN=",
                "CREEM_API_KEY=",
                "CREEM_WEBHOOK_SECRET=",
                "CREEM_API_BASE_URL=",
                "CREEM_PRODUCT_STANDARD_MONTHLY=",
                "CREEM_PRODUCT_STANDARD_ANNUAL=",
                "CREEM_PRODUCT_ALLSTAR_MONTHLY=",
                "CREEM_PRODUCT_ALLSTAR_ANNUAL=",
            ]
        )
    )
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "init",
            "--hosted",
            "--skip-docker-check",
            "--template-file",
            str(template_file),
            "--env-file",
            str(env_file),
        ],
        input=(
            "\n\n\n\n"
            "sk-test\n"
            "yahoo-id\n"
            "yahoo-secret\n"
            "discord-app\n"
            "discord-public\n"
            "discord-token\n"
            "creem-key\n"
            "creem-webhook\n"
            "\n"
            "standard-monthly\n"
            "standard-annual\n"
            "allstar-monthly\n"
            "allstar-annual\n"
        ),
    )

    assert result.exit_code == 0, result.output
    env_text = env_file.read_text()
    assert "CREEM_API_KEY=creem-key" in env_text
    assert "CREEM_WEBHOOK_SECRET=creem-webhook" in env_text
    assert "CREEM_PRODUCT_STANDARD_MONTHLY=standard-monthly" in env_text
    assert "CREEM_PRODUCT_ALLSTAR_ANNUAL=allstar-annual" in env_text
