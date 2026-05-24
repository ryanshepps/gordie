# Yahoo Fantasy OAuth Setup

Gordie reads your Yahoo Fantasy league via the Yahoo Fantasy Sports API. You need to register your own Yahoo developer app and copy the client credentials into `.env`.

## 1. Create the Cloudflare Tunnel

Gordie's default Docker stack runs `cloudflared` next to the server. Use a named Cloudflare Tunnel, not a Quick Tunnel, so the Yahoo redirect URI stays stable after restarts.

The easiest path is `uv run gordie init`. The setup wizard detects `cloudflared`, offers to install it when it is missing, opens the `cloudflared tunnel login` flow when needed, and can create the named tunnel plus DNS route for you. The Docker connector sends tunnel traffic to `http://server:8000`.

If you prefer the Cloudflare dashboard, open Cloudflare Zero Trust at https://one.dash.cloudflare.com/ and go to **Networks → Tunnels**.

1. Create a named Tunnel.
2. Add a public hostname such as `gordie.example.com`.
3. Point that hostname's service to:

```text
http://server:8000
```

`server` is the Docker Compose service name. Do not use `localhost:8000` inside the tunnel route; that would point at the `cloudflared` container itself.

4. Copy the tunnel token from Cloudflare's Docker connector command. It is the long `eyJ...` value passed after `--token`.

## 2. Register a Yahoo app

1. Sign in at https://developer.yahoo.com/apps/
2. Click **Create an App**.
3. Fill in:
   - **Application Name:** anything (e.g. "Gordie local")
   - **Application Type:** Web Application
   - **Redirect URI(s):** `https://your-public-host/callback`
     - This must exactly match your Cloudflare public hostname plus `/callback`.
   - **API Permissions:** check **Fantasy Sports — Read**
4. Submit. Yahoo issues a **Client ID (Consumer Key)** and **Client Secret (Consumer Secret)**.

## 3. Run setup

Run the setup wizard:

```bash
uv run gordie init
```

When the wizard creates the tunnel automatically, it writes the public URL and generated token into `.env`. If you skip automation, enter these values manually:

```bash
OAUTH_BASE_URL=https://your-public-host
CLOUDFLARED_TUNNEL_TOKEN=<cloudflare tunnel token>
YAHOO_CLIENT_ID=<consumer key>
YAHOO_CLIENT_SECRET=<consumer secret>
```

Then start or restart the stack:

```bash
docker compose up -d
```

## 4. Connect your league

Send a first message to Gordie:

```bash
uv run python scripts/message_agent.py --email you@example.com --message "hi"
```

Gordie replies with an OAuth link. Visit the URL, approve, get redirected back to `/callback?code=...`. Tokens land in `data/platform.db` (or the `yahoo_tokens` table in your Postgres if you've migrated to it).

## 5. Refresh + multi-team

The token store auto-refreshes via `refresh_token` whenever the access token expires. For accounts with multiple Fantasy teams, Gordie will ask which to track on the first message.

## Dev-only fallback: ngrok

ngrok is still useful for local experiments, but it is not Gordie's recommended self-hosted production path. If you use it, run:

```bash
ngrok http 8000
# Forwarding  https://abcd1234.ngrok-free.app -> http://localhost:8000
```

Use the `https://abcd1234.ngrok-free.app/callback` URL as the Yahoo redirect URI and as `OAUTH_BASE_URL` in `.env`. If the ngrok URL changes, update Yahoo and `.env` together.

## Troubleshooting

- **`invalid_redirect_uri`** — the URL in `.env` (`OAUTH_BASE_URL`) must exactly match what's registered in the Yahoo app, including the protocol, port, and trailing slash semantics.
- **`cloudflared` is running but callbacks fail** — confirm the Cloudflare public hostname routes to `http://server:8000` in the tunnel dashboard.
- **`Access blocked`** — Yahoo requires the app to be in "Active" status and the Fantasy Sports Read scope to be granted at app creation time.
- **`401` on subsequent calls** — the refresh token may have been revoked (e.g. user changed Yahoo password). Have the user re-authenticate.
