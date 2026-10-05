import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory

REPOSITORY = "ryanshepps/gordie"
OWNER = "ryanshepps"
CHECKS = {"PR title", "Lint", "Format", "Type Check", "Test"}


def run(
    *arguments: str,
    cwd: Path,
    authenticated: bool = False,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    allowed = {"PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "SYSTEMROOT"}
    if authenticated:
        allowed |= {"GH_TOKEN", "GITHUB_TOKEN"}
    environment = {key: value for key, value in os.environ.items() if key in allowed}
    environment.update(GH_HOST="github.com", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    return subprocess.run(
        arguments,
        cwd=cwd,
        env=environment,
        check=check,
        capture_output=capture,
        text=True,
        timeout=1800,
    )


def git(*arguments: str, cwd: Path, authenticated: bool = False) -> str:
    credentials = ("-c", "credential.helper=!gh auth git-credential") if authenticated else ()
    return run(
        "git",
        "-c",
        f"core.hooksPath={os.devnull}",
        "-c",
        "credential.helper=",
        *credentials,
        *arguments,
        cwd=cwd,
        authenticated=authenticated,
        capture=True,
    ).stdout.strip()


def github(*arguments: str, cwd: Path) -> str:
    return run("gh", *arguments, cwd=cwd, authenticated=True, capture=True).stdout.strip()


def validate(checkout: Path, artifacts: Path) -> tuple[Path, Path]:
    run("uv", "run", "--frozen", "ruff", "check", ".", cwd=checkout)
    run("uv", "run", "--frozen", "ruff", "format", "--check", ".", cwd=checkout)
    types = run(
        "uv",
        "run",
        "--frozen",
        "basedpyright",
        "--outputjson",
        cwd=checkout,
        capture=True,
        check=False,
    )
    report = json.loads(types.stdout)
    if report["summary"]["errorCount"]:
        raise RuntimeError("Type checking failed; release stopped.")
    run("uv", "run", "--frozen", "pytest", "tests/", "--ignore=tests/evals", cwd=checkout)
    run("uv", "build", "--out-dir", str(artifacts), cwd=checkout)
    (wheel,) = artifacts.glob("*.whl")
    (archive,) = artifacts.glob("*.tar.gz")
    run("uv", "run", "--frozen", "python", "scripts/check_package.py", str(wheel), cwd=checkout)
    return wheel, archive


def merge_release(checkout: Path, version: str) -> str:
    branch = f"release/v{version}"
    git("switch", "-c", branch, cwd=checkout)
    git("config", "user.name", OWNER, cwd=checkout)
    git("config", "user.email", f"{OWNER}@users.noreply.github.com", cwd=checkout)
    git("add", "pyproject.toml", "uv.lock", "CHANGELOG.md", cwd=checkout)
    git("commit", "-m", f"chore(release): prepare v{version}", cwd=checkout)
    head = git("rev-parse", "HEAD", cwd=checkout)
    git("push", "origin", f"HEAD:refs/heads/{branch}", cwd=checkout, authenticated=True)
    pull_request = github(
        "pr",
        "create",
        "--repo",
        REPOSITORY,
        "--base",
        "main",
        "--head",
        branch,
        "--title",
        f"chore(release): prepare v{version}",
        "--body",
        "Prepare Gordie's version and changelog with Commitizen.",
        cwd=checkout,
    )
    print(f"Release PR: {pull_request}", flush=True)
    deadline = time.monotonic() + 1800
    while time.monotonic() < deadline:
        names = json.loads(
            github(
                "pr",
                "view",
                pull_request,
                "--repo",
                REPOSITORY,
                "--json",
                "statusCheckRollup",
                "--jq",
                "[.statusCheckRollup[].name]",
                cwd=checkout,
            )
        )
        if CHECKS.issubset(names):
            break
        time.sleep(10)
    else:
        raise RuntimeError(f"CI did not start for {pull_request}; release stopped.")
    print(f"Waiting for CI before merging {pull_request}", flush=True)
    github(
        "pr",
        "checks",
        pull_request,
        "--repo",
        REPOSITORY,
        "--watch",
        "--fail-fast",
        "--interval",
        "10",
        cwd=checkout,
    )
    github(
        "pr",
        "merge",
        pull_request,
        "--repo",
        REPOSITORY,
        "--squash",
        "--match-head-commit",
        head,
        cwd=checkout,
    )
    merged = json.loads(
        github(
            "pr",
            "view",
            pull_request,
            "--repo",
            REPOSITORY,
            "--json",
            "state,mergeCommit",
            cwd=checkout,
        )
    )
    if merged["state"] != "MERGED":
        raise RuntimeError(f"{pull_request} is not merged; release stopped.")
    git("fetch", "origin", "main", cwd=checkout, authenticated=True)
    commit = merged["mergeCommit"]["oid"]
    if git("rev-parse", f"{commit}^{{tree}}", cwd=checkout) != git(
        "rev-parse", "HEAD^{tree}", cwd=checkout
    ):
        raise RuntimeError("Merged source differs from the validated source; release stopped.")
    return commit


def release(publish: bool) -> None:
    with TemporaryDirectory(prefix="gordie-release-") as directory:
        root = Path(directory)
        if publish:
            account = github("api", "--hostname", "github.com", "user", "--jq", ".login", cwd=root)
            if account != OWNER:
                raise RuntimeError(f"Publishing requires the {OWNER} GitHub account.")
        checkout = root / "source"
        git(
            "clone",
            "--branch",
            "main",
            "--single-branch",
            f"https://github.com/{REPOSITORY}.git",
            str(checkout),
            cwd=root,
            authenticated=publish,
        )
        git("fetch", "origin", "--tags", cwd=checkout, authenticated=publish)
        run("uv", "sync", "--frozen", cwd=checkout)
        current = run(
            "uv", "run", "--frozen", "cz", "version", "--project", cwd=checkout, capture=True
        ).stdout.strip()
        bump = bool(git("tag", "--list", f"v{current}", cwd=checkout))
        if bump:
            run(
                "uv", "run", "--frozen", "cz", "bump", "--yes", "--version-files-only", cwd=checkout
            )
        version = run(
            "uv", "run", "--frozen", "cz", "version", "--project", cwd=checkout, capture=True
        ).stdout.strip()
        tag = f"v{version}"
        if git("tag", "--list", tag, cwd=checkout):
            raise RuntimeError(f"{tag} already exists; release stopped.")
        print(f"Validating {REPOSITORY} {tag}", flush=True)
        wheel, archive = validate(checkout, root / "artifacts")
        if not publish:
            print(f"Dry run passed for {tag}. Run with --publish to create the release.")
            return
        commit = (
            merge_release(checkout, version) if bump else git("rev-parse", "HEAD", cwd=checkout)
        )
        github(
            "api",
            "--hostname",
            "github.com",
            f"repos/{REPOSITORY}/git/refs",
            "-f",
            f"ref=refs/tags/{tag}",
            "-f",
            f"sha={commit}",
            cwd=checkout,
        )
        notes = (
            ["--notes-file", str(checkout / "CHANGELOG.md")]
            if (checkout / "CHANGELOG.md").exists()
            else ["--generate-notes"]
        )
        url = github(
            "release",
            "create",
            tag,
            str(wheel),
            str(archive),
            "--repo",
            REPOSITORY,
            "--verify-tag",
            "--title",
            f"Gordie {tag}",
            *notes,
            cwd=checkout,
        )
        print(url)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and release Gordie from canonical main.")
    parser.add_argument(
        "--publish", action="store_true", help="Create and merge a release PR, tag, and publish."
    )
    arguments = parser.parse_args()
    try:
        release(arguments.publish)
    except (RuntimeError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        parser.exit(
            1, f"Release stopped: {error}\nRemote PRs or tags already created are retained.\n"
        )


if __name__ == "__main__":
    main()
