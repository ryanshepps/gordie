# Gordie — open source fantasy sports assistant

Gordie contains a Yahoo Fantasy account integration, sports data tools, an AI agent, billing support, and scheduled stats refreshes. User-facing messaging is currently unavailable while the communication integration is rebuilt.

## Current runtime

The Quart server exposes `/health`, Yahoo's `/callback`, and Creem billing routes when billing is configured. The scheduler refreshes NHL and MLB stats and cleans up expired OAuth requests. Weekly and news delivery jobs are inactive.

The command-line agent can still be used for local development:

```bash
uv run python -m gordie.scripts.message_agent you@example.com "What can you do?"
```

The account email remains the identity used by Yahoo and billing. The command prints the agent response locally.

## Project layout

- `src/gordie/agent/`: LangGraph agent, prompts, and analysis
- `src/gordie/client/`: Yahoo and sports data clients
- `src/gordie/data/`: account, token, and sports data models
- `src/gordie/scheduled/`: stats refresh and OAuth cleanup
- `src/gordie/server/`: Yahoo OAuth and optional billing HTTP routes
- `src/gordie/tools/`: agent tools
- `tests/`: focused unit, integration, and eval suites

Start with [the self-hosting quickstart](docs/setup/quickstart.md) or [Yahoo OAuth setup](docs/setup/yahoo-oauth.md).

## Python package

Published wheels are available from [GitHub Releases](https://github.com/ryanshepps/gordie/releases).
Install a release into a Python 3.13 environment:

```bash
uv pip install https://github.com/ryanshepps/gordie/releases/download/v0.1.0/gordie-0.1.0-py3-none-any.whl
```

Replace both version numbers with the release you want. Then import Gordie with
`from gordie import Plugins, create_app, create_agent` in your project.

Build locally with `uv build`. Install `dist/gordie-0.1.0-py3-none-any.whl` into a
Python 3.13 environment with `uv pip install`. The application imports under
`gordie`; it does not require the repository to be the working directory.

Use `gordie init --skip-docker-start` to generate configuration, `gordie-server`
to apply migrations and start the HTTP server, and
`gordie-message you@example.com "What can you do?"` to invoke the agent.
Load configuration into the environment or use a local `.env` file. Docker Compose
setup still requires the repository's Compose file and Dockerfile.

Set `GORDIE_DATA_DIR` to the writable directory for NHL and MLB statistics.
The default is `~/.local/share/gordie`. Persist this directory across container
restarts. Importing modules does not construct LLM clients or connect to PostgreSQL;
those resources initialize when used.

Verify an installed wheel outside the checkout with
`uv run python scripts/check_package.py dist/gordie-0.1.0-py3-none-any.whl`.

### Publishing a release

Only `ryanshepps` can publish through the **Publish Python package** workflow in
GitHub Actions. Select **Run workflow** with the `main` branch. Dispatches from
other accounts or branches, including reruns by other accounts, skip publishing.

For the first release, run the workflow after it is merged to publish the current
`0.1.0` version and establish the baseline tag.

For subsequent releases, prepare a local release PR with Commitizen:

```bash
git switch main
git pull --ff-only
git fetch --tags
uv sync --frozen
git switch -c release/next
uv run cz bump --yes --version-files-only
git add pyproject.toml uv.lock CHANGELOG.md
git commit -m "chore(release): bump version"
git push -u origin release/next
gh pr create --base main --title "chore(release): bump version" \
  --body "Prepare the next Gordie release with Commitizen."
```

Commitizen calculates the next version from commits since the current version's
tag, updates `pyproject.toml` and `uv.lock`, and generates `CHANGELOG.md`.
`--version-files-only` leaves committing and tagging to the PR and publishing
workflow, so the release tag points to the merged commit. Use a fresh branch name
for each release PR. Merge the release PR after CI passes, then run the publishing
workflow on `main`.

Use Conventional Commit PR titles and squash merges so Commitizen can classify
changes. CI checks PR titles. `fix:`, `perf:`, and `refactor:` bump the patch
version; `feat:` bumps the minor version. While Gordie is below `1.0`, breaking
changes (`feat!:` or a `BREAKING CHANGE:` footer) also bump the minor version.
Remove `major_version_zero` from the Commitizen configuration when adopting
stable `1.x` versioning. Documentation and chore commits do not trigger a bump;
Commitizen stops if there are no release-worthy commits.

The workflow reads the version through Commitizen, builds and verifies the wheel,
creates a `v<version>` tag at the selected commit, and uploads the wheel and source
archive to a GitHub Release. An existing tag or release causes publishing to fail;
published files are not replaced.

## Integration interface

Use `from gordie import Plugins, create_app, create_agent` to assemble Gordie with
your own storage, access policy, extra tools, and communication adapter for incoming
messages and outgoing replies. Models, memory, statistics, application routes, and
background jobs remain built into Gordie. The existing PostgreSQL and
Creem implementations remain in this repository under `gordie.integrations`.

See [the plugin interface and lifecycle guide](docs/plugins.md) for contracts,
assembly examples, and the future private-package boundary.

## License

AGPL-3.0 — see [LICENSE](LICENSE).
