#!/bin/bash
# Deploy the frontend (SvelteKit) to Cloudflare Pages
set -e

if [ -z "$CLOUDFLARE_API_TOKEN" ]; then
  echo "Error: CLOUDFLARE_API_TOKEN is not set. Export it before running this script."
  exit 1
fi

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

# Cloudflare Pages project name — update this to match your Pages project
PAGES_PROJECT="gordie-website"

echo "Building frontend..."
cd "$FRONTEND_DIR"
pnpm install --frozen-lockfile
pnpm build

echo ""
echo "Deploying frontend to Cloudflare Pages..."
pnpm exec wrangler pages deploy .svelte-kit/cloudflare --project-name "$PAGES_PROJECT"

echo ""
echo "Deploy complete!"
