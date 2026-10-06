# Configuration

`.env.example` is the runtime template. `uv run gordie init` writes a local `.env`.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Postgres for accounts, Yahoo tokens, and agent state |
| `OAUTH_BASE_URL` | Public HTTPS URL for Yahoo's `/callback` |
| `NGROK_AUTHTOKEN` | Default Docker tunnel authentication |
| `SERVER_HOST`, `SERVER_PORT` | HTTP bind address |
| `YAHOO_CLIENT_ID`, `YAHOO_CLIENT_SECRET` | Yahoo Fantasy OAuth |
| `LLM_MODEL` | OpenRouter chat model ID |
| `EMBEDDING_MODEL` | OpenRouter model ID for conversation search; defaults to `openai/text-embedding-3-small` |
| `EMBEDDING_DIMENSIONS` | Embedding vector size; must match the selected model (default `1536`) |
| `OPENROUTER_API_KEY` | OpenRouter API key |
| `ENABLED_SPORTS` | Stats refresh selection: `nhl` by default |
| `OSS_GITHUB_URL` | Repository link in the maintenance server |

No user messaging provider is configured. The Yahoo email address is retained as an account identifier.
