# Gordie — open source fantasy sports assistant

Gordie contains a Yahoo Fantasy account integration, sports data tools, an AI agent, and scheduled stats refreshes. User-facing messaging is currently unavailable while the communication integration is rebuilt.

## Current runtime

The Quart server exposes `/health` and Yahoo's `/callback`. The scheduler refreshes NHL stats and cleans up expired OAuth requests. Weekly and news delivery jobs are inactive.

The command-line agent can still be used for local development:

```bash
uv run python -m gordie.scripts.message_agent you@example.com "What can you do?"
```

The account email remains the identity used by Yahoo. The command prints the agent response locally.

## Project layout

- `src/gordie/agent/`: LangGraph agent, prompts, and analysis
- `src/gordie/client/`: Yahoo and sports data clients
- `src/gordie/data/`: account, token, and sports data models
- `src/gordie/scheduled/`: stats refresh and OAuth cleanup
- `src/gordie/server/`: Yahoo OAuth HTTP routes
- `src/gordie/tools/`: agent tools
- `tests/`: focused unit, integration, and eval suites

Start with [the self-hosting quickstart](docs/setup/quickstart.md) or [Yahoo OAuth setup](docs/setup/yahoo-oauth.md).

## Python package

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

## Integration interface

Use `from gordie import Plugins, create_app, create_agent` to assemble Gordie with
your own storage, access policy, extra tools, and communication adapter for incoming
messages and outgoing replies. Models, memory, statistics, application routes, and
background jobs remain built into Gordie. The existing PostgreSQL implementation
remains in this repository under `gordie.integrations`.

See [the plugin interface and lifecycle guide](docs/plugins.md) for contracts,
assembly examples, and the future private-package boundary.

## License

AGPL-3.0 — see [LICENSE](LICENSE).
