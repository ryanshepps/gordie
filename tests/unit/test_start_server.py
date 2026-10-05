"""Tests for server startup."""

from collections.abc import Mapping
from importlib.resources import files

import pytest
from alembic.config import Config
from pytest import MonkeyPatch

from gordie.integrations import migrations
from gordie.integrations.config_validator import ConfigValidationError
from gordie.scripts import start_server


def test_run_migrations_upgrades_to_head(monkeypatch: MonkeyPatch) -> None:
    calls: list[tuple[str | None, str]] = []

    def upgrade_database(config: Config, revision: str) -> None:
        calls.append((config.config_file_name, revision))

    monkeypatch.setattr(migrations, "upgrade_database", upgrade_database)

    migrations.run_migrations()

    assert calls == [(str(files("gordie").joinpath("resources/alembic.ini")), "head")]


def test_should_redirect_stderr_defaults_to_file_logging(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("GORDIE_LOG_FILE", raising=False)

    assert start_server.should_redirect_stderr()


def test_should_redirect_stderr_skips_console_logging(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("GORDIE_LOG_FILE", "stderr")

    assert not start_server.should_redirect_stderr()


def test_main_validates_config_before_server_creation(monkeypatch: MonkeyPatch) -> None:
    calls: list[str] = []

    def validate_startup_config(_env: Mapping[str, str]) -> None:
        calls.append("validate")
        raise ConfigValidationError(missing=(), invalid=("bad config",))

    monkeypatch.setattr(start_server, "validate_startup_config", validate_startup_config)

    with pytest.raises(SystemExit) as exc_info:
        start_server.main()

    assert exc_info.value.code == 1
    assert calls == ["validate"]


def test_main_runs_server_after_valid_config(monkeypatch: MonkeyPatch) -> None:
    calls: list[str] = []

    class FakeServer:
        def run(self) -> None:
            calls.append("run")

    def validate_startup_config(_env: Mapping[str, str]) -> None:
        calls.append("validate")

    def create_server(host: str, port: int) -> FakeServer:
        calls.append(f"create:{host}:{port}")
        return FakeServer()

    monkeypatch.setenv("SERVER_HOST", "127.0.0.1")
    monkeypatch.setenv("SERVER_PORT", "9000")
    monkeypatch.setenv("GORDIE_LOG_FILE", "stderr")
    monkeypatch.setattr(start_server, "validate_startup_config", validate_startup_config)
    monkeypatch.setattr(start_server, "create_server", create_server)

    start_server.main()

    assert calls == ["validate", "create:127.0.0.1:9000", "run"]
