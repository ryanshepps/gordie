#!/bin/bash
# Deploy script for fantasy-agent OAuth server and Cloudflare tunnel
# This script unloads and reloads the macOS launch agents

set -e

OAUTH_PLIST="$HOME/Library/LaunchAgents/com.fantasy-agent.oauth.plist"
TUNNEL_PLIST="$HOME/Library/LaunchAgents/com.fantasy-agent.tunnel.plist"

echo "🚀 Deploying fantasy-agent services..."
echo ""

# Unload services
echo "📴 Unloading services..."
if launchctl list | grep -q "com.fantasy-agent.oauth"; then
    launchctl unload "$OAUTH_PLIST" 2>/dev/null || echo "  ⚠️  OAuth service was not running"
    echo "  ✓ OAuth service unloaded"
else
    echo "  ℹ️  OAuth service was not loaded"
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
launchctl load "$OAUTH_PLIST"
echo "  ✓ OAuth service loaded"

launchctl load "$TUNNEL_PLIST"
echo "  ✓ Tunnel service loaded"

# Wait a moment for services to start
sleep 2

# Check status
echo ""
echo "📊 Service status:"
if launchctl list | grep -q "com.fantasy-agent.oauth"; then
    echo "  ✓ OAuth service: Running"
else
    echo "  ✗ OAuth service: Not running"
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
echo "  OAuth:  tail -f oauth.log oauth-error.log"
echo "  Tunnel: tail -f tunnel.log tunnel-error.log"
