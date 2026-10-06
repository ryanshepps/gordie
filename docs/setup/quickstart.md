# Quickstart

Gordie currently exposes Yahoo OAuth, health checks, stats refresh, and a local command-line agent. User messaging is unavailable.

## Prerequisites

- Docker and Docker Compose
- [uv](https://docs.astral.sh/uv/)
- A public HTTPS callback URL (the default Docker stack uses ngrok)
- A Yahoo developer app with Fantasy Sports Read access
- An OpenAI or Anthropic API key

## Configure and start

```bash
uv run gordie init
curl http://localhost:8000/health
```

The wizard creates `.env`, configures the Yahoo callback URL, and starts the Docker stack. It can configure ngrok and detect your stable dev domain. Configure Yahoo's redirect URI as `OAUTH_BASE_URL/callback`.

## Run the local agent

```bash
uv run python -m gordie.scripts.message_agent you@example.com "What can you do?"
```

The response prints to the terminal. For Yahoo data, follow the authorization URL returned by the agent. The callback saves the Yahoo tokens; run the command again for fantasy analysis. There is no email, SMS, or chat delivery.

## Focused checks

```bash
uv run pytest tests/ --ignore=tests/evals
uv run ruff check .
uv run ruff format --check .
```

See [test guidance](../../tests/README.md) for the slow eval suite.

## Troubleshooting

- If startup validation fails, fill in the missing variables named in the server log.
- If Yahoo rejects the redirect, confirm the public `OAUTH_BASE_URL/callback` matches the developer app exactly.
- If the first stats refresh takes time, it downloads the NHL dataset. `ENABLED_SPORTS=nhl` enables the startup refresh.
