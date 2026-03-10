"""Tests for the run_moneypuck_query tool."""

import subprocess
from unittest.mock import patch

from tools.stats.run_moneypuck_query import run_moneypuck_query


def _make_completed_process(stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )


class TestRunMoneypuckQuery:

    def test_passes_command_args_to_subprocess(self):
        """Should split command and pass args to subprocess.run."""
        mock_output = '{"name": "Connor McDavid", "goals": 20}'
        with patch(
            "tools.stats.run_moneypuck_query.subprocess.run",
            return_value=_make_completed_process(stdout=mock_output),
        ) as mock_run:
            result = run_moneypuck_query.invoke(
                {"command": "player stats 'Connor McDavid' --json"}
            )

            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert args[0] == "uv"
            assert args[1] == "run"
            assert args[2] == "moneypuckpy"
            assert "player" in args
            assert "stats" in args
            assert "--json" in args

        assert mock_output in result

    def test_returns_stdout_on_success(self):
        """Should return stdout when command succeeds."""
        expected = '{"goals": 10, "assists": 15}'
        with patch(
            "tools.stats.run_moneypuck_query.subprocess.run",
            return_value=_make_completed_process(stdout=expected),
        ):
            result = run_moneypuck_query.invoke({"command": "player stats 'Test' --json"})

        assert result == expected

    def test_returns_error_on_nonzero_exit(self):
        """Should return error message when command fails."""
        with patch(
            "tools.stats.run_moneypuck_query.subprocess.run",
            return_value=_make_completed_process(
                stderr="Player not found", returncode=1
            ),
        ):
            result = run_moneypuck_query.invoke({"command": "player stats 'Nobody' --json"})

        assert "failed" in result.lower() or "error" in result.lower()

    def test_handles_timeout(self):
        """Should return timeout error when command takes too long."""
        with patch(
            "tools.stats.run_moneypuck_query.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="test", timeout=30),
        ):
            result = run_moneypuck_query.invoke({"command": "player stats 'Slow' --json"})

        assert "timed out" in result.lower()

    def test_passes_timeout_to_subprocess(self):
        """Should pass 30s timeout to subprocess.run."""
        with patch(
            "tools.stats.run_moneypuck_query.subprocess.run",
            return_value=_make_completed_process(stdout="{}"),
        ) as mock_run:
            run_moneypuck_query.invoke({"command": "search 'Test' --json"})

            _, kwargs = mock_run.call_args
            assert kwargs["timeout"] == 30
            assert kwargs["capture_output"] is True
            assert kwargs["text"] is True
