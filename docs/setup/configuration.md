# Configuration Reference

Every runtime knob is an environment variable read at process start. `.env.example` is the canonical template. This page expands on the non-obvious ones.

## Core

| Var | Required | Default | Notes |
|-----|----------|---------|-------|
| `DATABASE_URL` | Yes | `postgresql://localhost:5432/fantasy_agent` | psycopg v3 driver is injected automatically — no need to write `postgresql+psycopg://`. |
| `OAUTH_BASE_URL` | Yes (for Yahoo) | `http://localhost:8000` | Public HTTPS URL Yahoo redirects to. Must match the redirect URI on your Yahoo app. |
| `SERVER_HOST` | No | `localhost` | Bind address. Set to `0.0.0.0` inside Docker (already set in the image). |
| `SERVER_PORT` | No | `8000` | |

## LLM

| Var | Required | Default | Notes |
|-----|----------|---------|-------|
| `LLM_PROVIDER` | No | `openai` | Values: `openai`, `anthropic`. Sub-agents are currently OpenAI-only (see `agent/subagents/base.py`) because they rely on OpenAI's `parallel_tool_calls=False` binding. The main supervisor + voice rewrite + digest writer + quality + intent classifier all honor this. |
| `LLM_MODEL` | No | `gpt-4o-mini` | Provider-specific model name. For Anthropic, use `claude-sonnet-4-5` or similar. |
| `OPENAI_API_KEY` | If `LLM_PROVIDER=openai` | — | |
| `ANTHROPIC_API_KEY` | If `LLM_PROVIDER=anthropic` | — | |

## Sport gating

| Var | Required | Default | Notes |
|-----|----------|---------|-------|
| `ENABLED_SPORTS` | No | `nhl,mlb` | Comma-separated. Disables the corresponding stats DB refresh on startup. The agent tools themselves are still registered — sport filtering happens later via `middleware/sport_tool_filter.py`. |

## Hosted trial

| Var | Required | Default | Notes |
|-----|----------|---------|-------|
| `TRIAL_TTL_DAYS` | No | `7` | Temporary web sessions expire after this many days. |
| `TRIAL_QUESTION_LIMIT` | No | `5` | Applied to both the browser session and the connected Yahoo account. |
| `TRIAL_RETURN_URL` | No | `VITE_SITE_URL` or `http://localhost:5173` | Frontend URL linked from the Yahoo OAuth success page. |
| `TRIAL_COOKIE_SECURE` | No | inferred from `OAUTH_BASE_URL` | Set `false` for local HTTP testing and `true` behind HTTPS. |

## Web process scaling

Scheduled jobs currently run inside the web process. Keep the web service at exactly one replica until issue #36 moves those jobs to a worker.

| Var | Required | Default | Notes |
|-----|----------|---------|-------|
| `WEB_PROCESS_REPLICA_COUNT` | No | `1` | Startup fails if this is not `1`, unless the override below is set. |
| `ALLOW_IN_PROCESS_SCHEDULER_SCALE` | No | `false` | Emergency override only; duplicate scheduled jobs can run when scaled. |

## External services

See per-service setup docs:
- `yahoo-oauth.md` — `YAHOO_CLIENT_ID`, `YAHOO_CLIENT_SECRET`
- `email-mailgun.md` — `MAILGUN_API_KEY`, `MAILGUN_DOMAIN`, `MAILGUN_FROM_EMAIL`, `MAILGUN_WEBHOOK_SIGNING_KEY`
- `sms-sinch.md` — `SINCH_SERVICE_PLAN_ID`, `SINCH_API_TOKEN`, `SINCH_FROM_NUMBER`, `SINCH_WEBHOOK_TOKEN`
- `discord.md` — `DISCORD_MODE`, `DISCORD_APPLICATION_ID`, `DISCORD_PUBLIC_KEY`, `DISCORD_BOT_TOKEN`

## Billing (Creem)

| Var | Required | Default | Notes |
|-----|----------|---------|-------|
| `CREEM_API_KEY` | No | empty | Leave empty to disable billing. Calls return 4xx; tier enforcement falls back to "all features enabled". |
| `CREEM_WEBHOOK_SECRET` | If using Creem webhooks | — | |
| `CREEM_API_BASE_URL` | No | `https://test-api.creem.io/v1` | Use the prod URL for live customers. |
| `CREEM_PRODUCT_STANDARD_MONTHLY` etc. | If using Creem | — | Map tier → Creem product ID. |

## Frontend (`frontend/.env` or Cloudflare Pages env)

| Var | Default | Notes |
|-----|---------|-------|
| `VITE_API_URL` | `http://localhost:8000` | Backend base URL the SvelteKit site calls. |
| `VITE_SITE_URL` | `http://localhost:5173` | Used for sitemap + RSS + canonical URLs. |
| `VITE_ALLOWED_HOSTS` | empty | Comma-separated extra hosts for the Vite dev server (e.g. `my-mac.local`). |
