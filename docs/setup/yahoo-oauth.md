# Yahoo Fantasy OAuth Setup

Gordie reads your Yahoo Fantasy league via the Yahoo Fantasy Sports API. You need to register your own Yahoo developer app and copy the client credentials into `.env`.

## 1. Register a Yahoo app

1. Sign in at https://developer.yahoo.com/apps/
2. Click **Create an App**.
3. Fill in:
   - **Application Name:** anything (e.g. "Gordie local")
   - **Application Type:** Web Application
   - **Redirect URI(s):** `https://your-public-host/callback`
     - For local dev, this **must be HTTPS** — see step 2 for the ngrok option.
   - **API Permissions:** check **Fantasy Sports — Read**
4. Submit. Yahoo issues a **Client ID (Consumer Key)** and **Client Secret (Consumer Secret)**.

## 2. Local HTTPS for the callback

Yahoo refuses plain HTTP callback URLs even in dev. The fastest local option is ngrok:

```bash
brew install ngrok
ngrok http 8000
# Forwarding  https://abcd1234.ngrok-free.app -> http://localhost:8000
```

Use the `https://abcd1234.ngrok-free.app/callback` URL as the Yahoo redirect URI and as `OAUTH_BASE_URL` in `.env`.

## 3. Set env vars

```bash
YAHOO_CLIENT_ID=<consumer key>
YAHOO_CLIENT_SECRET=<consumer secret>
OAUTH_BASE_URL=https://your-public-host
```

Restart the server (`docker compose restart server`) for the new env to take effect.

## 4. Connect your league

Send a first message to Gordie:

```bash
uv run python scripts/message_agent.py --email you@example.com --message "hi"
```

Gordie replies with an OAuth link. Visit the URL, approve, get redirected back to `/callback?code=...`. Tokens land in `data/platform.db` (or the `yahoo_tokens` table in your Postgres if you've migrated to it).

## 5. Refresh + multi-team

The token store auto-refreshes via `refresh_token` whenever the access token expires. For accounts with multiple Fantasy teams, Gordie will ask which to track on the first message.

## Troubleshooting

- **`invalid_redirect_uri`** — the URL in `.env` (`OAUTH_BASE_URL`) must exactly match what's registered in the Yahoo app, including the protocol, port, and trailing slash semantics.
- **`Access blocked`** — Yahoo requires the app to be in "Active" status and the Fantasy Sports Read scope to be granted at app creation time.
- **`401` on subsequent calls** — the refresh token may have been revoked (e.g. user changed Yahoo password). Have the user re-authenticate.
