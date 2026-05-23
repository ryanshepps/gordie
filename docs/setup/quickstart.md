# Quickstart — Self-Host Gordie

The fastest path to a working local instance. ~15 minutes.

## Prerequisites

- Docker + Docker Compose
- [uv](https://docs.astral.sh/uv/) for Python (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Node.js 22 + pnpm (for the frontend) — `mise install` works if you use mise
- An OpenAI API key (Anthropic also supported — see configuration)

You do **not** need Mailgun, Sinch, Discord, Creem, or Cloudflare to boot the server. Those are optional integrations layered on top.

## 1. Clone and configure

```bash
git clone https://github.com/ryanshepps/gordie.git
cd gordie

uv run gordie init
```

The setup wizard writes `.env`, verifies Docker is installed, prompts for your chat medium, LLM provider, Yahoo app credentials, and skips hosted billing unless you pass `--hosted`.

## 2. Start Postgres + the server

```bash
docker compose up -d
curl http://localhost:8000/health
# {"status":"ok"}
```

The server applies Alembic migrations automatically before it starts accepting requests.

## 3. Send Gordie a message without configuring email

The fastest sanity check:

```bash
uv run python scripts/message_agent.py \
  --email you@example.com \
  --message "What can you do?"
```

Output appears in `server.log` (tail it: `docker compose logs -f server`).

To do anything fantasy-specific (lineups, trades, waivers), follow `yahoo-oauth.md` to wire up your own Yahoo dev app.

## 4. Run the frontend (optional)

```bash
cd frontend
pnpm install
pnpm dev
# http://localhost:5173
```

The frontend is a marketing site + signup flow. It hits the backend at `VITE_API_URL` (defaults to `http://localhost:8000`).

## 5. Run tests

```bash
uv run pytest tests/unit                  # no external services
uv run pytest tests/evals/test_<file>.py  # specific eval (slow if you run all of them)
```

See `tests/README.md` for which suites need which credentials.

## Next steps

- `docs/setup/yahoo-oauth.md` — register a Yahoo Fantasy app
- `docs/setup/email-mailgun.md` — wire up inbound/outbound email
- `docs/setup/sms-sinch.md` — wire up SMS (optional; consider swapping Twilio)
- `docs/setup/discord.md` — wire up Discord slash commands (optional)
- `docs/setup/configuration.md` — full env-var reference

## Troubleshooting

- **`MAILGUN_API_KEY ... not set` warning** — expected if you haven't configured email. Email send returns `error: email_disabled`.
- **Yahoo OAuth callback fails** — Yahoo requires HTTPS for production callbacks. For local dev, point `OAUTH_BASE_URL` at an HTTPS tunnel pointing to `localhost:8000`.
- **`refresh_stats_db` errors on startup** — first boot downloads MoneyPuck NHL CSV (~30 MB) and MLB stats. Slow but non-blocking. Set `ENABLED_SPORTS=nhl` (or `mlb`) to skip the other.
