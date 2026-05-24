"""Tests for application logger configuration."""

import logging
from logging.handlers import RotatingFileHandler

from pytest import MonkeyPatch

from module.logger import get_logger


def test_get_logger_uses_stderr_when_env_requests_it(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("module.logger._is_test_environment", lambda: False)
    monkeypatch.setenv("GORDIE_LOG_FILE", "stderr")
    logger = get_logger("tests.unit.logger.stderr")

    try:
        assert any(isinstance(handler, logging.StreamHandler) for handler in logger.handlers)
        assert not any(isinstance(handler, RotatingFileHandler) for handler in logger.handlers)
    finally:
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()
