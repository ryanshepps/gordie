#!/usr/bin/env bash
set -euo pipefail

publish=false
if [[ $# == 1 && $1 == --publish ]]; then
    publish=true
elif [[ $# != 0 ]]; then
    echo "Usage: $0 [--publish]" >&2
    exit 1
fi

run() (
    while IFS= read -r variable; do
        case "$variable" in
            PATH|HOME|TMPDIR|GH_TOKEN|GITHUB_TOKEN) ;;
            *) unset "$variable" ;;
        esac
    done < <(compgen -e)
    export GH_HOST=github.com GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
    command "$@"
)
gh() { run gh "$@"; }
git() {
    run git -c core.hooksPath=/dev/null -c credential.helper= \
        -c 'credential.helper=!gh auth git-credential' "$@"
}
uv() ( unset GH_TOKEN GITHUB_TOKEN; run uv "$@"; )

repo=ryanshepps/gordie
if $publish && [[ $(gh api user --jq .login) != ryanshepps ]]; then
    echo "Publishing requires the ryanshepps GitHub account." >&2
    exit 1
fi

release_dir=$(mktemp -d "${TMPDIR:-/tmp}/gordie-release.XXXXXX")
trap 'rm -rf -- "$release_dir"' EXIT
git clone --branch main --single-branch "https://github.com/$repo.git" "$release_dir/source"
cd "$release_dir/source"
git fetch origin --tags
uv sync --frozen

version=$(uv run --frozen cz version --project)
bumped=false
if git show-ref --verify --quiet "refs/tags/v$version"; then
    uv run --frozen cz bump --yes --version-files-only
    version=$(uv run --frozen cz version --project)
    bumped=true
fi

uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen basedpyright --level ERROR
uv run --frozen pytest tests/ --ignore=tests/evals
uv build
uv run --frozen python scripts/check_package.py dist/*.whl

if ! $publish; then
    echo "Dry run passed for v$version. Use --publish to release."
    exit 0
fi

if $bumped; then
    branch="release/v$version"
    git switch -c "$branch"
    git config user.name ryanshepps
    git config user.email ryanshepps@users.noreply.github.com
    git add pyproject.toml uv.lock CHANGELOG.md
    git commit -m "chore(release): prepare v$version"
    head=$(git rev-parse HEAD)
    git push origin "HEAD:refs/heads/$branch"
    pr=$(gh pr create --repo "$repo" --base main --head "$branch" \
        --title "chore(release): prepare v$version" --body "Prepare the next Gordie release.")
    echo "Release PR: $pr"

    for ((attempt=0; attempt<60; attempt++)); do
        checks=$(gh pr view "$pr" --repo "$repo" --json statusCheckRollup --jq '.statusCheckRollup | length')
        ((checks >= 5)) && break
        sleep 5
    done
    ((checks >= 5)) || { echo "CI did not start; release stopped." >&2; exit 1; }
    gh pr checks "$pr" --repo "$repo" --watch --fail-fast
    gh pr merge "$pr" --repo "$repo" --squash --match-head-commit "$head"
    commit=$(gh pr view "$pr" --repo "$repo" --json state,mergeCommit \
        --jq 'if .state == "MERGED" then .mergeCommit.oid else empty end')
    [[ -n "$commit" ]]
    git fetch origin main
    [[ $(git rev-parse "$commit^{tree}") == $(git rev-parse 'HEAD^{tree}') ]]
else
    commit=$(git rev-parse HEAD)
fi

gh api "repos/$repo/git/refs" -f "ref=refs/tags/v$version" -f "sha=$commit"
notes=(--generate-notes)
if [[ -f CHANGELOG.md ]]; then
    notes=(--notes-file CHANGELOG.md)
fi
gh release create "v$version" dist/*.whl dist/*.tar.gz --repo "$repo" \
    --verify-tag --title "Gordie v$version" "${notes[@]}"
