---
name: gordie-codereview-guide
description: Project-specific review guidelines for Gordie
triggers:
  - /codereview
---

# Gordie Code Review Guidelines

In addition to the default OpenHands code review checks, verify these project
conventions:

## Python and Tooling

- Python commands should use `uv`.
- Do not introduce `typing.Any`; prefer concrete types, `Mapping`, `Sequence`,
  type aliases, or explicit unions.
- Keep changes consistent with the existing module boundaries under `agent/`,
  `client/`, `data/`, `scheduled/`, and `server/`.

## Tests

- Tests should validate behavior rather than implementation details.
- Tests should not overlap existing test coverage.
- Avoid running or requiring the full eval suite for unrelated changes; only
  targeted evals should be required when a change affects eval behavior.

## PR Completeness

- Inspect adjacent domains, callers, configuration, documentation, migrations,
  tests, and operational references that are implied by the PR's stated intent.
- Flag missing follow-through when the changed code creates an incomplete user
  flow, stale documentation, untested behavior, or mismatched configuration.
- Keep completeness feedback tied to the PR's actual intent; do not request
  unrelated cleanup or speculative follow-up work.

## Operations

- Database changes should include Alembic migrations when schema changes are
  introduced.
- Deployment changes should account for the existing `scripts/deploy.sh`
  deployment path.
