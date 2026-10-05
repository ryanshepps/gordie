import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
import tomlkit


@pytest.fixture(autouse=True)
def isolated_git_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    result = subprocess.run(
        ["git", "rev-parse", "--local-env-vars"], check=True, capture_output=True, text=True
    )
    for name in result.stdout.splitlines():
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize(
    ("message", "expected_version"),
    [
        ("fix: correct player lookup", "0.1.1"),
        ("perf: speed up player lookup", "0.1.1"),
        ("refactor: simplify player lookup", "0.1.1"),
        ("feat: add player lookup", "0.2.0"),
        ("feat!: change player lookup contract", "0.2.0"),
    ],
)
def test_commitizen_prepares_release_files(
    tmp_path: Path, message: str, expected_version: str
) -> None:
    prepare_repository(tmp_path, message)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "commitizen",
            "bump",
            "--yes",
            "--version-files-only",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    with (tmp_path / "pyproject.toml").open("rb") as manifest:
        assert tomllib.load(manifest)["project"]["version"] == expected_version
    with (tmp_path / "uv.lock").open("rb") as lockfile:
        packages = tomllib.load(lockfile)["package"]
    assert (
        next(package["version"] for package in packages if package["name"] == "gordie")
        == expected_version
    )
    assert f"v{expected_version}" in (tmp_path / "CHANGELOG.md").read_text()
    assert git(tmp_path, "tag", "--list").stdout.strip() == "v0.1.0"
    assert git(tmp_path, "log", "-1", "--format=%s").stdout.strip() == message


def test_commitizen_does_not_release_documentation_only_changes(tmp_path: Path) -> None:
    prepare_repository(tmp_path, "docs: clarify player lookup")
    result = subprocess.run(
        [sys.executable, "-m", "commitizen", "bump", "--yes", "--version-files-only"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 21
    assert not (tmp_path / "CHANGELOG.md").exists()
    assert not git(tmp_path, "status", "--porcelain").stdout


def prepare_repository(directory: Path, message: str) -> None:
    root = Path(__file__).resolve().parents[2]
    manifest = tomlkit.parse((root / "pyproject.toml").read_text())
    manifest["project"]["version"] = "0.1.0"
    (directory / "pyproject.toml").write_text(tomlkit.dumps(manifest))
    lockfile = tomlkit.parse((root / "uv.lock").read_text())
    for package in lockfile["package"]:
        if package["name"] == "gordie":
            package["version"] = "0.1.0"
    (directory / "uv.lock").write_text(tomlkit.dumps(lockfile))
    git(directory, "init")
    git(directory, "config", "user.name", "Release test")
    git(directory, "config", "user.email", "release-test@example.com")
    git(directory, "config", "commit.gpgsign", "false")
    git(directory, "add", "pyproject.toml", "uv.lock")
    git(directory, "commit", "-m", "chore: initialize release baseline")
    git(directory, "tag", "v0.1.0")
    git(directory, "commit", "--allow-empty", "-m", message)


def git(directory: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments], cwd=directory, check=True, capture_output=True, text=True
    )
