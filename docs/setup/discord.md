# Discord Setup

Discord is optional. Gordie supports two Discord modes:

- `gateway`: local bot mode. Gordie opens an outbound Discord Gateway websocket, so Discord chat does not need a public tunnel.
- `interactions`: hosted slash-command mode. Discord sends signed HTTP requests to `/discord/interactions`, so Gordie needs a public HTTPS endpoint.

## 1. Create a Discord application

1. Open the Discord Developer Portal and create an application.
2. Copy the application ID.
3. If using gateway mode, create a bot, copy its token, enable Message Content Intent, and invite it to your server.
4. If using interactions mode, add a slash command named `gordie` with a string option named `question`, then copy the public key.

## 2. Configure environment variables

`uv run gordie init` configures gateway mode for local Docker installs:

```bash
DISCORD_MODE=gateway
DISCORD_APPLICATION_ID=<application id>
DISCORD_BOT_TOKEN=<bot token>
DISCORD_ALLOWED_USER_IDS=<your discord user id>
DISCORD_REQUIRE_MENTION=true
```

`uv run gordie init --hosted` configures interactions mode for hosted installs:

```bash
DISCORD_MODE=interactions
DISCORD_APPLICATION_ID=<application id>
DISCORD_PUBLIC_KEY=<public key>
```

Yahoo OAuth still uses the shared callback URL:

```bash
OAUTH_BASE_URL=https://your-public-host
NGROK_AUTHTOKEN=<ngrok authtoken>
YAHOO_CLIENT_ID=<consumer key>
YAHOO_CLIENT_SECRET=<consumer secret>
```

Gateway mode removes the public URL requirement for Discord chat. It does not remove Yahoo's OAuth callback requirement; Yahoo still redirects the user to `OAUTH_BASE_URL/callback` through the ngrok tunnel.

## 3. Configure the interaction endpoint

Skip this section for gateway mode.

For interactions mode, set the Discord interaction endpoint URL to:

```text
https://your-public-host/discord/interactions
```

The route verifies Discord's Ed25519 signature using `DISCORD_PUBLIC_KEY`, returns a deferred response immediately, and edits the original Discord response after the agent finishes.

## 4. How Discord responses are sent

Interactions mode delivery is implemented as a channel adapter in `server/adapters/discord_adapter.py`.
The route stores the latest interaction token for each Discord conversation thread in `discord_interaction_targets`; the adapter looks up that token and edits the original deferred response.

Gateway mode runs a Discord bot client inside the server process. Direct messages are forwarded to Gordie. Server messages are forwarded only when the bot is mentioned unless `DISCORD_REQUIRE_MENTION=false`.

Core agent code only depends on the adapter registry, so Discord-specific request parsing, signature verification, token storage, and response editing stay outside the agent graph.

## 5. Limitations

Discord interaction tokens expire 15 minutes after Discord issues them. In interactions mode, Gordie sends a deferred acknowledgement immediately, then edits the original Discord response after the agent finishes. If processing exceeds Discord's token window, Discord rejects the edit and the failure is logged.

Keep Discord question processing comfortably under 15 minutes. Long-running future workflows should move to a durable job/status flow or a separate notification path instead of relying on the original interaction token.
