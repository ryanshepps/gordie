"""Setup wizard behavior without a messaging provider."""

from pathlib import Path

from typer.testing import CliRunner

from gordie.integrations.config_validator import validate_startup_config
from gordie.scripts.setup import (
    DeploymentTarget,
    SetupAnswers,
    app,
    build_env_values,
    render_env_file,
)


def test_build_env_values_keeps_yahoo_without_retired_config() -> None:
    answers = SetupAnswers(
        deployment_target=DeploymentTarget.DOCKER,
        values={
            "OAUTH_BASE_URL": "https://gordie.example.com",
            "NGROK_AUTHTOKEN": "test-tunnel",
            "OPENROUTER_API_KEY": "test-model",
            "YAHOO_CLIENT_ID": "test-yahoo-id",
            "YAHOO_CLIENT_SECRET": "test-yahoo-secret",
        },
    )

    values = build_env_values(answers, admin_api_key="test-admin")

    validate_startup_config(values)
    assert values["YAHOO_CLIENT_ID"] == "test-yahoo-id"
    assert values["LLM_MODEL"] == "z-ai/glm-5.3-flash"
    assert values["EMBEDDING_MODEL"] == "openai/text-embedding-3-small"
    assert values["EMBEDDING_DIMENSIONS"] == "1536"
    assert "CREEM_API_KEY" not in values
    assert "CHAT_MEDIA" not in values
    assert not any(
        key.startswith(("DISCORD_", "SINCH_", "MAILGUN_", "TELEGRAM_")) for key in values
    )


def test_build_env_values_accepts_custom_embedding_settings() -> None:
    answers = SetupAnswers(
        deployment_target=DeploymentTarget.DOCKER,
        values={
            "OAUTH_BASE_URL": "https://gordie.example.com",
            "NGROK_AUTHTOKEN": "test-tunnel",
            "OPENROUTER_API_KEY": "test-key",
            "YAHOO_CLIENT_ID": "test-yahoo-id",
            "YAHOO_CLIENT_SECRET": "test-yahoo-secret",
            "EMBEDDING_MODEL": "test/embedding-model",
            "EMBEDDING_DIMENSIONS": "768",
        },
    )

    values = build_env_values(answers, admin_api_key="test-admin")

    validate_startup_config(values)
    assert values["EMBEDDING_MODEL"] == "test/embedding-model"
    assert values["EMBEDDING_DIMENSIONS"] == "768"


def test_render_env_file_keeps_account_settings() -> None:
    rendered = render_env_file(
        "YAHOO_CLIENT_ID=\nOPENROUTER_API_KEY=\nLLM_PROVIDER=openai\nOPENAI_API_KEY=old\n",
        {
            "YAHOO_CLIENT_ID": "test-yahoo",
            "OPENROUTER_API_KEY": "test-model",
        },
    )

    assert "YAHOO_CLIENT_ID=test-yahoo" in rendered
    assert "OPENROUTER_API_KEY=test-model" in rendered
    assert "OPENAI_API_KEY" not in rendered
    assert "LLM_PROVIDER" not in rendered


def test_init_rejects_missing_template(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "init",
            "--template-file",
            str(tmp_path / "missing.env.example"),
            "--env-file",
            str(tmp_path / ".env"),
        ],
    )

    assert result.exit_code == 1
    assert "does not exist" in result.output


def test_init_removes_retired_config(tmp_path: Path, monkeypatch) -> None:
    template = tmp_path / ".env.example"
    env_file = tmp_path / ".env"
    template.write_text("OAUTH_BASE_URL=\nYAHOO_CLIENT_ID=\n")
    env_file.write_text(
        "CHAT_MEDIA=telegram\nTELEGRAM_BOT_TOKEN=test-retired\nCREEM_API_KEY=test-retired\n"
    )
    answers = SetupAnswers(
        deployment_target=DeploymentTarget.DOCKER,
        values={
            "OAUTH_BASE_URL": "https://gordie.example.com",
            "NGROK_AUTHTOKEN": "test-tunnel",
            "OPENROUTER_API_KEY": "test-model",
            "YAHOO_CLIENT_ID": "test-yahoo-id",
            "YAHOO_CLIENT_SECRET": "test-yahoo-secret",
        },
    )
    monkeypatch.setattr("gordie.scripts.setup._prompt_for_answers", lambda **_kwargs: answers)

    result = CliRunner().invoke(
        app,
        [
            "init",
            "--skip-docker-start",
            "--template-file",
            str(template),
            "--env-file",
            str(env_file),
        ],
    )

    assert result.exit_code == 0, result.output
    generated = env_file.read_text()
    assert "TELEGRAM_BOT_TOKEN" not in generated
    assert "CHAT_MEDIA" not in generated
    assert "CREEM_API_KEY" not in generated
    assert "YAHOO_CLIENT_ID=test-yahoo-id" in generated
