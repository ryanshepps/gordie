# Configuration

`.env.example` is the runtime template. `uv run gordie init` writes a local `.env`.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Postgres for accounts, Yahoo tokens, billing, and agent state |
| `OAUTH_BASE_URL` | Public HTTPS URL for Yahoo's `/callback` |
| `NGROK_AUTHTOKEN` | Default Docker tunnel authentication |
| `SERVER_HOST`, `SERVER_PORT` | HTTP bind address |
| `YAHOO_CLIENT_ID`, `YAHOO_CLIENT_SECRET` | Yahoo Fantasy OAuth |
| `LLM_PROVIDER`, `LLM_MODEL` | Agent model selection |
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` | Key for the selected model provider |
| `ENABLED_SPORTS` | Stats refresh selection: `nhl,mlb` by default |
| `CREEM_API_KEY`, `CREEM_WEBHOOK_SECRET`, `CREEM_PRODUCT_HOSTED_MONTHLY` | Optional billing |
| `OSS_GITHUB_URL` | Repository link in the maintenance server |

No user messaging provider is configured. The Yahoo email address is retained as an account identifier.
