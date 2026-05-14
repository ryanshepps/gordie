# Cloudflare Tunnel (Local HTTPS)

A free way to expose your local server at a stable HTTPS subdomain. Useful for Yahoo OAuth callbacks and Mailgun/Sinch inbound webhooks during development.

## 1. Install cloudflared

```bash
brew install cloudflared       # macOS
# or: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
```

## 2. Auth + create a tunnel

```bash
cloudflared tunnel login                    # opens browser, pick a zone
cloudflared tunnel create gordie            # prints a UUID + writes ~/.cloudflared/<uuid>.json
cloudflared tunnel route dns gordie fantasy.example.com
```

Move the credentials JSON into the project so it can be ignored by git:

```bash
mkdir -p .cloudflared
mv ~/.cloudflared/<uuid>.json .cloudflared/
```

## 3. Config file

Copy the example and fill in your UUID + hostname:

```bash
cp config/cloudflare-tunnel-config.example.yml config/cloudflare-tunnel-config.yml
```

Edit:

```yaml
tunnel: <your-uuid>
credentials-file: ./.cloudflared/<your-uuid>.json
ingress:
  - hostname: fantasy.example.com
    service: http://localhost:8000
  - service: http_status:404
```

## 4. Run

```bash
./scripts/start_tunnel.sh
```

This boots the tunnel and the server in parallel. Hit `https://fantasy.example.com/health` — should return `{"status":"ok"}`.

## 5. Set the env var

In `.env`:

```bash
OAUTH_BASE_URL=https://fantasy.example.com
```

Restart the server so Yahoo OAuth URLs use the public host.

## Cleanup

```bash
cloudflared tunnel delete gordie
```
