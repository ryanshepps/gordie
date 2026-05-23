"""Tests for the Gordie setup CLI."""

from pathlib import Path

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
    render_env_file,
)


def test_parse_chat_media_requires_at_least_one_medium() -> None:
    try:
        _ = parse_chat_media(" ")
    except SetupInputError as exc:
        assert "at least one" in str(exc)
    else:
        raise AssertionError("Expected empty chat media to fail")


def test_parse_chat_media_rejects_unknown_medium() -> None:
    try:
        _ = parse_chat_media("telegram, slack")
    except SetupInputError as exc:
        assert "slack" in str(exc)
        assert "telegram, discord, email, sms" in str(exc)
    else:
        raise AssertionError("Expected unknown chat media to fail")


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

    try:
        _ = build_env_values(answers, admin_api_key="admin-token")
    except SetupInputError as exc:
        assert "SINCH_API_TOKEN" in str(exc)
    else:
        raise AssertionError("Expected missing required keys to fail")


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


def test_init_command_writes_env_file(tmp_path: Path) -> None:
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
                "TELEGRAM_BOT_TOKEN=",
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
        input="\n\n\n\nsk-test\nyahoo-id\nyahoo-secret\ntelegram-token\n",
    )

    assert result.exit_code == 0, result.output
    env_text = env_file.read_text()
    assert "CHAT_MEDIA=telegram" in env_text
    assert "LLM_PROVIDER=openai" in env_text
    assert "OPENAI_API_KEY=sk-test" in env_text
    assert "YAHOO_CLIENT_ID=yahoo-id" in env_text
    assert "TELEGRAM_BOT_TOKEN=telegram-token" in env_text
    assert "CREEM_API_KEY=" in env_text
    assert "docker compose up -d" in result.output


def test_init_command_rejects_existing_env_without_force(tmp_path: Path) -> None:
    template_file = tmp_path / ".env.example"
    env_file = tmp_path / ".env"
    _ = template_file.write_text("OPENAI_API_KEY=\n")
    _ = env_file.write_text("OPENAI_API_KEY=keep-me\n")
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
    )

    assert result.exit_code == 1
    assert "already exists" in result.output
    assert env_file.read_text() == "OPENAI_API_KEY=keep-me\n"


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
                "TELEGRAM_BOT_TOKEN=",
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
            "telegram-token\n"
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
