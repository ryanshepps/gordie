# Yahoo Fantasy OAuth Setup

Gordie reads your Yahoo Fantasy league via the Yahoo Fantasy Sports API. You need to register your own Yahoo developer app and copy the client credentials into `.env`.

## 1. Configure ngrok

Gordie's default Docker stack runs `ngrok` next to the server. ngrok gives every account a stable dev domain, so you do not need to own a domain for Yahoo OAuth.

The easiest path is `uv run gordie init`. The setup wizard detects `ngrok`, offers to install it when it is missing, asks for your ngrok authtoken, briefly starts ngrok to detect your dev-domain URL, and writes that URL to `.env`.

Get your authtoken at https://dashboard.ngrok.com/get-started/your-authtoken.

The Docker connector sends tunnel traffic to:

```text
http://server:8000
```

`server` is the Docker Compose service name. Do not use `localhost:8000` inside the Docker tunnel command; that would point at the `ngrok` container itself.

## 2. Register a Yahoo app

1. Sign in at https://developer.yahoo.com/apps/
2. Click **Create an App**.
3. Fill in:
   - **Application Name:** anything, for example "Gordie local"
   - **Application Type:** Web Application
   - **Redirect URI(s):** `https://your-ngrok-dev-domain.ngrok-free.app/callback`
     - This must exactly match the `OAUTH_BASE_URL` written by setup plus `/callback`.
   - **API Permissions:** check **Fantasy Sports - Read**
4. Submit. Yahoo issues a **Client ID (Consumer Key)** and **Client Secret (Consumer Secret)**.

## 3. Run setup

Run the setup wizard:

```bash
uv run gordie init
```

When the wizard configures ngrok automatically, it writes the public URL and authtoken into `.env`. If you skip automation, enter these values manually:

```bash
OAUTH_BASE_URL=https://your-ngrok-dev-domain.ngrok-free.app
NGROK_AUTHTOKEN=<ngrok authtoken>
YAHOO_CLIENT_ID=<consumer key>
YAHOO_CLIENT_SECRET=<consumer secret>
```

`uv run gordie init` starts the Docker Compose stack by default. Restart it manually only if you changed `.env` after setup, skipped Docker startup, or the services are stopped:

```bash
docker compose up -d --build
```

If local health fails, run `docker compose ps` and `docker compose logs -f server ngrok`.
If the public callback fails, run `curl "$OAUTH_BASE_URL/health"` and confirm Yahoo is configured with `OAUTH_BASE_URL` plus `/callback`.

## 4. Connect your league

Send a first message to Gordie:

```bash
uv run python scripts/message_agent.py you@example.com "hi"
```

Gordie replies with an OAuth link. Visit the URL, approve, get redirected back to `/callback?code=...`. Tokens land in `data/platform.db` (or the `yahoo_tokens` table in your Postgres if you've migrated to it).

## 5. Refresh + multi-team

The token store auto-refreshes via `refresh_token` whenever the access token expires. For accounts with multiple Fantasy teams, Gordie will ask which to track on the first message.

## Troubleshooting

- **`invalid_redirect_uri`** — the URL in `.env` (`OAUTH_BASE_URL`) must exactly match what's registered in the Yahoo app, including the protocol, port, and trailing slash semantics.
- **`ngrok` is running but callbacks fail** — confirm the Yahoo redirect URI is `OAUTH_BASE_URL` plus `/callback`, then check `docker compose logs -f ngrok`.
- **`ngrok` exits on startup** — confirm `NGROK_AUTHTOKEN` is set in `.env` and came from https://dashboard.ngrok.com/get-started/your-authtoken.
- **`Access blocked`** — Yahoo requires the app to be in "Active" status and the Fantasy Sports Read scope to be granted at app creation time.
- **`401` on subsequent calls** — the refresh token may have been revoked, for example if the user changed their Yahoo password. Have the user re-authenticate.
