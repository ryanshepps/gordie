# CLAUDE.md

## Tools

This project uses `uv`. Always use `uv` when running Python commands.

## Tests

Tests should not test implementation details and should not overlap one another.

The entire eval test suite takes a long time to run. You should only run the evals that are relevant to your changes.

## Types

Never use `Any` from `typing`. Use specific types, `Mapping`, `Sequence`, type aliases, or union types instead.

## Logs

Logs are located in the root directory with the `.log` extension. These are large files — use tail, head, and grep to view smaller chunks.

## Gstack

Always use the `/browse` skill from gstack for web browsing. Never use `mcp__claude-in-chrome__*` tools.

Available skills: `/office-hours`, `/plan-ceo-review`, `/plan-eng-review`, `/plan-design-review`, `/design-consultation`, `/review`, `/ship`, `/land-and-deploy`, `/canary`, `/benchmark`, `/browse`, `/qa`, `/qa-only`, `/design-review`, `/setup-browser-cookies`, `/setup-deploy`, `/retro`, `/investigate`, `/document-release`, `/codex`, `/cso`, `/autoplan`, `/careful`, `/freeze`, `/guard`, `/unfreeze`, `/gstack-upgrade`.

## Deployment

Deployment is made through the ./scripts/deploy.sh script