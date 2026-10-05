# Gordie — open source fantasy sports assistant

Gordie contains a Yahoo Fantasy account integration, sports data tools, an AI agent, billing support, and scheduled stats refreshes. User-facing messaging is currently unavailable while the communication integration is rebuilt.

## Current runtime

The Quart server exposes `/health`, Yahoo's `/callback`, and Creem billing routes when billing is configured. The scheduler refreshes NHL stats and cleans up expired OAuth requests. Weekly and news delivery jobs are inactive.

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

Set `GORDIE_DATA_DIR` to the writable directory for NHL statistics.
The default is `~/.local/share/gordie`. Persist this directory across container
restarts. Importing modules does not construct LLM clients or connect to PostgreSQL;
those resources initialize when used.

Verify an installed wheel outside the checkout with
`uv run python scripts/check_package.py dist/gordie-0.1.0-py3-none-any.whl`.

### Publishing a release

Use the local release script after this PR is merged. It requires Python 3.13,
`uv`, Git, and the GitHub CLI. Preview a release without remote changes:

```bash
uv run python scripts/release.py
```

To publish, authenticate `gh` to github.com as `ryanshepps` and opt in explicitly:

```bash
gh auth login --hostname github.com
uv run python scripts/release.py --publish
```

The script clones `ryanshepps/gordie` at `main` into a temporary directory,
calculates the next version with Commitizen, updates both version files and the
changelog, and runs lint, format, type, non-eval tests, build, and installed-wheel
checks. It opens a release PR, waits for CI, and squash-merges it without bypassing
branch protection. It verifies that the merged source matches the validated
source before tagging and uploading the wheel and source archive to GitHub Releases.
The first release publishes the current `0.1.0` version to establish the baseline.
If a version bump is already merged but untagged, it validates and publishes that
version without creating another release PR.

Only the authenticated `ryanshepps` account passes the publishing guard; GitHub
permissions remain the authority for remote writes. No credentials are stored in
the script or repository. GitHub tokens are passed only to authenticated Git/GitHub
commands, and application secrets are excluded from all subprocess environments.
Builds and tests execute trusted canonical code locally; this is not a sandbox.
Run the script from a trusted checkout with trusted tools.

Your working tree is untouched, and the temporary checkout is removed on exit.
The script does not force-push, replace existing tags or releases, or use admin
merge overrides. Failures stop the release; any remote PR or tag already created
remains for inspection and recovery. Required reviews or a merge queue can stop
automatic completion. An existing tag without a release needs manual recovery
before retrying; it will not be overwritten.

Use Conventional Commit PR titles and squash merges so Commitizen can classify
changes. CI checks PR titles. `fix:`, `perf:`, and `refactor:` bump the patch
version; `feat:` bumps the minor version. While Gordie is below `1.0`, breaking
changes (`feat!:` or a `BREAKING CHANGE:` footer) also bump the minor version.
Remove `major_version_zero` from the Commitizen configuration when adopting
stable `1.x` versioning. Documentation and chore commits do not trigger a bump;
Commitizen stops if there are no release-worthy commits.

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
