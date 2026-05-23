"""Tests for server startup."""

from alembic.config import Config
from pytest import MonkeyPatch

from scripts import start_server


def test_run_migrations_upgrades_to_head(monkeypatch: MonkeyPatch) -> None:
    calls: list[tuple[str | None, str]] = []

    def upgrade_database(config: Config, revision: str) -> None:
        calls.append((config.config_file_name, revision))

    monkeypatch.setattr(start_server, "upgrade_database", upgrade_database)

    start_server.run_migrations()

    assert calls == [("alembic.ini", "head")]


def test_should_redirect_stderr_defaults_to_file_logging(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("GORDIE_LOG_FILE", raising=False)

    assert start_server.should_redirect_stderr()


def test_should_redirect_stderr_skips_console_logging(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("GORDIE_LOG_FILE", "stderr")

    assert not start_server.should_redirect_stderr()
