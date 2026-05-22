# Configuration Reference

Every runtime knob is an environment variable read at process start. `.env.example` is the canonical template. This page expands on the non-obvious ones.

## Core

| Var | Required | Default | Notes |
|-----|----------|---------|-------|
| `DATABASE_URL` | Yes | `postgresql://localhost:5432/fantasy_agent` | psycopg v3 driver is injected automatically — no need to write `postgresql+psycopg://`. |
| `ADMIN_API_KEY` | Yes (if using `/admin/*`) | empty | Generate with `openssl rand -hex 32`. Empty value → all admin endpoints return 401. |
| `ENVIRONMENT` | No | `development` | Affects tracing init + log verbosity. Values: `development`, `production`. |
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

## Memory

| Var | Required | Default | Notes |
|-----|----------|---------|-------|
| `MEMORY_ENABLED` | No | `true` | Set to `false` to disable conversation memory. Semantic conversation search uses OpenAI embeddings only when `LLM_PROVIDER=openai` and `OPENAI_API_KEY` is set; Anthropic-only deployments start without OpenAI and report past-conversation search as unavailable. |

## External services

See per-service setup docs:
- `yahoo-oauth.md` — `YAHOO_CLIENT_ID`, `YAHOO_CLIENT_SECRET`
- `email-mailgun.md` — `MAILGUN_API_KEY`, `MAILGUN_DOMAIN`, `MAILGUN_FROM_EMAIL`, `MAILGUN_WEBHOOK_SIGNING_KEY`
- `sms-sinch.md` — `SINCH_SERVICE_PLAN_ID`, `SINCH_API_TOKEN`, `SINCH_FROM_NUMBER`, `SINCH_WEBHOOK_TOKEN`
- `cloudflare-tunnel.md` — `CLOUDFLARE_API_TOKEN`, `CF_TUNNEL_ID`, `CF_TUNNEL_HOSTNAME`

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
