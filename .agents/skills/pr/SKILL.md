---
name: pr
description: Create or update a verified pull request for Gordie, run local CI and targeted evals, and comment the actual results. Use when asked to create, open, or ship a PR.
---

# PR

1. Fetch the latest default branch and merge it into the working branch. Stop for non-trivial conflicts.
2. Run the local checks from `.github/workflows/ci.yml`: `uv run ruff check .`, `uv run ruff format --check .`, the Basedpyright error gate, and `uv run pytest tests/ --ignore=tests/evals`. The Basedpyright gate fails on errors; its warnings and notes are informational. Fix failures before continuing.
3. Run only eval files under `tests/evals/` relevant to the change with `uv run pytest tests/evals/test_<name>.py`. Record each selected file and its result. If no eval applies, say so; do not run the full eval suite.
4. Run applicable build checks: `uv build` for Python packaging changes; `pnpm --dir frontend check` and `pnpm --dir frontend build` for frontend changes. Record only checks actually run.
5. Review the diff, stage only intentional files, and commit using the repository's commit style.
6. Push and create or update a concise PR. Check mergeability and wait for hosted CI results. Fix failures before reporting success.
7. Comment on the PR with the local checks and evals actually run:

| CI check | Result |
| --- | --- |
| `<command>` | ✅ Passed / ❌ Failed |

| Eval | Result |
| --- | --- |
| `<file or description>` | ✅ Passed / ❌ Failed |

Include hosted CI status separately. Omit empty tables and never report an unrun check as passed.
