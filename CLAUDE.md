# CLAUDE.md

## Tools

This project uses `uv`. Always use `uv` when running Python commands.

## Types

Never use `Any` from `typing`. Use specific types, `Mapping`, `Sequence`, type aliases, or union types instead.

## Logs

Logs are located in the root directory with the `.log` extension. These are large files — use tail, head, and grep to view smaller chunks.
