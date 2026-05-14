#!/bin/bash
# Start the Cloudflare Tunnel + server.
# Expects a config file at config/cloudflare-tunnel-config.yml
# (copy config/cloudflare-tunnel-config.example.yml and fill in your tunnel UUID).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="${CF_TUNNEL_CONFIG:-$PROJECT_ROOT/config/cloudflare-tunnel-config.yml}"

if [ ! -f "$CONFIG_FILE" ]; then
  echo "Tunnel config not found at: $CONFIG_FILE"
  echo "Copy config/cloudflare-tunnel-config.example.yml and set CF_TUNNEL_CONFIG, or"
  echo "place the file at the default path."
  exit 1
fi

echo "Starting Cloudflare Tunnel..."
# Tunnel identity comes from the `tunnel:` field in the config file —
# no CLI name arg needed, avoiding mismatch when multiple tunnels exist.
cloudflared tunnel --config "$CONFIG_FILE" run &

echo "Starting server..."
(cd "$PROJECT_ROOT" && uv run python -m scripts.start_server) &

wait
