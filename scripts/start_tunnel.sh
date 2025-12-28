#!/bin/bash
# Start the Cloudflare Tunnel for server callbacks

CONFIG_FILE="/Users/ryan/Projects/fantasy-agent-prod/config/cloudflare-tunnel-config.yml"

echo "Starting Cloudflare Tunnel..."
cloudflared tunnel --config "$CONFIG_FILE" run fantasy-server &

echo "Starting server..."
uv run python -m scripts.start_server &

# Wait for both background processes
wait
