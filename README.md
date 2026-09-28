# Gordie — open source fantasy sports assistant

Gordie contains a Yahoo Fantasy account integration, sports data tools, an AI agent, billing support, and scheduled stats refreshes. User-facing messaging and website signup are currently unavailable while the communication integration is rebuilt.

## Current runtime

The Quart server exposes `/health`, Yahoo's `/callback`, and Creem billing routes when billing is configured. The scheduler refreshes NHL and MLB stats and cleans up expired OAuth requests. Weekly and news delivery jobs are inactive.

The command-line agent can still be used for local development:

```bash
uv run python scripts/message_agent.py you@example.com "What can you do?"
```

The account email remains the identity used by Yahoo and billing. The command prints the agent response locally.

## Project layout

- `agent/`: LangGraph agent, prompts, and analysis
- `client/`: Yahoo and sports data clients
- `data/`: account, token, and sports data models
- `frontend/`: SvelteKit project website
- `scheduled/`: stats refresh and OAuth cleanup
- `server/`: Yahoo OAuth and optional billing HTTP routes
- `tools/`: agent tools
- `tests/`: focused unit, integration, and eval suites

Start with [the self-hosting quickstart](docs/setup/quickstart.md) or [Yahoo OAuth setup](docs/setup/yahoo-oauth.md).

## License

AGPL-3.0 — see [LICENSE](LICENSE).
