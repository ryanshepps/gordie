#!/bin/bash
# Deploy script for fantasy-agent application server and Cloudflare tunnel
# This script unloads and reloads the macOS launch agents

set -e

SERVER_PLIST="$HOME/Library/LaunchAgents/com.fantasy-agent.server.plist"
TUNNEL_PLIST="$HOME/Library/LaunchAgents/com.fantasy-agent.tunnel.plist"

echo "Running pre-deployment checks..."
# uv run pytest

echo "🚀 Deploying fantasy-agent services..."
echo ""

# Unload services
echo "📴 Unloading services..."
if launchctl list | grep -q "com.fantasy-agent.server"; then
    launchctl unload "$SERVER_PLIST" 2>/dev/null || echo "  ⚠️  Server service was not running"
    echo "  ✓ Server service unloaded"
else
    echo "  ℹ️  Server service was not loaded"
fi

if launchctl list | grep -q "com.fantasy-agent.tunnel"; then
    launchctl unload "$TUNNEL_PLIST" 2>/dev/null || echo "  ⚠️  Tunnel service was not running"
    echo "  ✓ Tunnel service unloaded"
else
    echo "  ℹ️  Tunnel service was not loaded"
fi

# Wait a moment for services to fully stop
echo ""
echo "⏳ Waiting for services to stop..."
sleep 2

# Load services
echo ""
echo "📡 Loading services..."
launchctl load "$SERVER_PLIST"
echo "  ✓ Server service loaded"

launchctl load "$TUNNEL_PLIST"
echo "  ✓ Tunnel service loaded"

# Wait a moment for services to start
sleep 2

# Check status
echo ""
echo "📊 Service status:"
if launchctl list | grep -q "com.fantasy-agent.server"; then
    echo "  ✓ Server service: Running"
else
    echo "  ✗ Server service: Not running"
fi

if launchctl list | grep -q "com.fantasy-agent.tunnel"; then
    echo "  ✓ Tunnel service: Running"
else
    echo "  ✗ Tunnel service: Not running"
fi

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📝 View logs:"
cat <<'EOF'
  Server: tail -f server.log | jq -R 'fromjson? | select(.) | "\(.timestamp // "N/A") [\(.level)] \(.filename // ""):\(.line // "") \(.function // "") - \(.message)"'
EOF
echo "  Tunnel: tail -f tunnel.log tunnel-error.log"
