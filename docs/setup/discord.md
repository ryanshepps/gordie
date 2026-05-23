# Discord Setup

Discord is optional. When `DISCORD_PUBLIC_KEY` or `DISCORD_APPLICATION_ID` is unset, Discord interaction handling returns `503` and the rest of the server still boots normally.

## 1. Create a Discord application

1. Open the Discord Developer Portal and create an application.
2. Add a slash command named `gordie` with a string option named `question`.
3. Copy the application ID and public key.

## 2. Configure environment variables

```bash
DISCORD_APPLICATION_ID=<application id>
DISCORD_PUBLIC_KEY=<public key>
```

Yahoo OAuth still uses the shared callback URL:

```bash
OAUTH_BASE_URL=https://your-public-host
YAHOO_CLIENT_ID=<consumer key>
YAHOO_CLIENT_SECRET=<consumer secret>
```

## 3. Configure the interaction endpoint

Set the Discord interaction endpoint URL to:

```text
https://your-public-host/discord/interactions
```

The route verifies Discord's Ed25519 signature using `DISCORD_PUBLIC_KEY`, returns a deferred response immediately, and edits the original Discord response after the agent finishes.

## 4. How Discord responses are sent

Discord delivery is implemented as a channel adapter in `server/adapters/discord_adapter.py`.
The route stores the latest interaction token for each Discord conversation thread in `discord_interaction_targets`; the adapter looks up that token and edits the original deferred response.

Core agent code only depends on the adapter registry, so Discord-specific request parsing, signature verification, token storage, and response editing stay outside the agent graph.

## 5. Limitations

Discord interaction tokens expire 15 minutes after Discord issues them. Gordie sends a deferred acknowledgement immediately, then edits the original Discord response after the agent finishes. If processing exceeds Discord's token window, Discord rejects the edit and the failure is logged.

Keep Discord question processing comfortably under 15 minutes. Long-running future workflows should move to a durable job/status flow or a separate notification path instead of relying on the original interaction token.
