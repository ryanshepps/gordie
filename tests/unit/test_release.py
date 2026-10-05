import json
import subprocess
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from scripts import release as release_script


@pytest.mark.parametrize("authenticated", [False, True])
def test_release_subprocess_credentials_are_scoped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture, authenticated: bool
) -> None:
    monkeypatch.setenv("GH_TOKEN", "test-token")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("GIT_DIR", "/unrelated/repository")
    monkeypatch.setenv("GH_HOST", "unrelated.example")
    process = mocker.patch(
        "scripts.release.subprocess.run", return_value=subprocess.CompletedProcess([], 0)
    )
    release_script.run("gh" if authenticated else "uv", cwd=tmp_path, authenticated=authenticated)
    environment = process.call_args.kwargs["env"]
    assert ("GH_TOKEN" in environment) == authenticated
    assert "OPENAI_API_KEY" not in environment
    assert "GIT_DIR" not in environment
    assert environment["GH_HOST"] == "github.com"
    assert environment["GIT_CONFIG_GLOBAL"]
    assert "shell" not in process.call_args.kwargs


def simulate_release(
    monkeypatch: pytest.MonkeyPatch,
    *,
    account: str = "ryanshepps",
    bump: bool = False,
    fail_ci: bool = False,
    merged_tree: str = "validated-tree",
) -> list[tuple[str, ...]]:
    commands: list[tuple[str, ...]] = []
    bumped = False

    def run(
        *arguments: str,
        cwd: Path,
        authenticated: bool = False,
        check: bool = True,
        capture: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        nonlocal bumped
        commands.append(arguments)
        output = ""
        if arguments[:2] == ("gh", "api") and "user" in arguments:
            output = account
        elif "clone" in arguments:
            Path(arguments[-1]).mkdir()
        elif "--project" in arguments:
            output = "0.1.1" if bumped else "0.1.0"
        elif "bump" in arguments:
            bumped = True
        elif "--list" in arguments and arguments[-1] == "v0.1.0" and bump:
            output = "v0.1.0"
        elif "HEAD^{tree}" in arguments:
            output = "validated-tree"
        elif "merged-commit^{tree}" in arguments:
            output = merged_tree
        elif "rev-parse" in arguments:
            output = "validated-commit"
        elif arguments[:3] == ("gh", "pr", "create"):
            output = "https://github.com/ryanshepps/gordie/pull/100"
        elif "statusCheckRollup" in arguments:
            output = json.dumps(sorted(release_script.CHECKS))
        elif "state,mergeCommit" in arguments:
            output = json.dumps({"state": "MERGED", "mergeCommit": {"oid": "merged-commit"}})
        elif arguments[:3] == ("gh", "pr", "checks") and fail_ci:
            raise subprocess.CalledProcessError(1, arguments)
        return subprocess.CompletedProcess(arguments, 0, stdout=output, stderr="")

    def validate(checkout: Path, artifacts: Path) -> tuple[Path, Path]:
        commands.append(("validate",))
        return artifacts / "gordie.whl", artifacts / "gordie.tar.gz"

    monkeypatch.setattr(release_script, "run", run)
    monkeypatch.setattr(release_script, "validate", validate)
    return commands


@pytest.mark.parametrize("authenticated", [False, True])
def test_release_git_uses_credentials_only_when_requested(
    tmp_path: Path, mocker: MockerFixture, authenticated: bool
) -> None:
    process = mocker.patch(
        "scripts.release.subprocess.run",
        return_value=subprocess.CompletedProcess([], 0, stdout="", stderr=""),
    )
    release_script.git("status", cwd=tmp_path, authenticated=authenticated)
    arguments = process.call_args.args[0]
    assert ("credential.helper=!gh auth git-credential" in arguments) == authenticated
    assert "credential.helper=" in arguments


def test_release_rejects_other_accounts_before_cloning(monkeypatch: pytest.MonkeyPatch) -> None:
    commands = simulate_release(monkeypatch, account="another-user")
    with pytest.raises(RuntimeError, match="requires the ryanshepps"):
        release_script.release(True)
    assert len(commands) == 1


def test_release_dry_run_has_no_remote_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    commands = simulate_release(monkeypatch, bump=True)
    release_script.release(False)
    assert any("https://github.com/ryanshepps/gordie.git" in command for command in commands)
    assert ("validate",) in commands
    assert not any(command[0] == "gh" or "push" in command for command in commands)


def test_initial_release_publishes_validated_main(monkeypatch: pytest.MonkeyPatch) -> None:
    commands = simulate_release(monkeypatch)
    release_script.release(True)
    tag = next(command for command in commands if "ref=refs/tags/v0.1.0" in command)
    assert "sha=validated-commit" in tag
    assert not any(command[:2] == ("gh", "pr") or "push" in command for command in commands)
    assert commands.index(("validate",)) < commands.index(tag)
    publication = next(
        command for command in commands if command[:3] == ("gh", "release", "create")
    )
    assert "--verify-tag" in publication
    assert "ryanshepps/gordie" in publication


def test_release_waits_for_ci_and_merges_exact_head_before_tagging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands = simulate_release(monkeypatch, bump=True)
    release_script.release(True)
    merge = next(command for command in commands if command[:3] == ("gh", "pr", "merge"))
    checks = next(command for command in commands if command[:3] == ("gh", "pr", "checks"))
    tag = next(command for command in commands if "ref=refs/tags/v0.1.1" in command)
    assert (
        commands.index(("validate",))
        < commands.index(checks)
        < commands.index(merge)
        < commands.index(tag)
    )
    assert "--admin" not in merge
    assert "--match-head-commit" in merge and "validated-commit" in merge
    assert "sha=merged-commit" in tag
    assert not any("--force" in command for command in commands)


def test_release_failed_ci_never_merges_or_publishes(monkeypatch: pytest.MonkeyPatch) -> None:
    commands = simulate_release(monkeypatch, bump=True, fail_ci=True)
    with pytest.raises(subprocess.CalledProcessError):
        release_script.release(True)
    assert not any(command[:3] == ("gh", "pr", "merge") for command in commands)
    assert not any("git/refs" in " ".join(command) for command in commands)


def test_release_failed_validation_has_no_remote_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    commands = simulate_release(monkeypatch, bump=True)

    def fail_validation(checkout: Path, artifacts: Path) -> tuple[Path, Path]:
        raise RuntimeError("Package validation failed")

    monkeypatch.setattr(release_script, "validate", fail_validation)
    with pytest.raises(RuntimeError, match="validation failed"):
        release_script.release(True)
    assert not any("push" in command or command[:2] == ("gh", "pr") for command in commands)
    assert not any("git/refs" in " ".join(command) for command in commands)


def test_release_changed_merge_tree_never_tags(monkeypatch: pytest.MonkeyPatch) -> None:
    commands = simulate_release(monkeypatch, bump=True, merged_tree="different-tree")
    with pytest.raises(RuntimeError, match="differs from the validated"):
        release_script.release(True)
    assert not any("git/refs" in " ".join(command) for command in commands)
