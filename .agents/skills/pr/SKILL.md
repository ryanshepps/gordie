---
name: pr
description: Create or update a verified pull request for Gordie, run targeted evals, and comment the actual results. Use when asked to create, open, update or ship a PR.
---

# PR

1. Fetch the latest default branch and merge it into the working branch. Stop for non-trivial conflicts.
2. Run the local checks from `.github/workflows/ci.yml`. Fix failures before continuing.
3. Review the diff, stage only intentional files, and commit using the repository's commit style.
4. Run only eval files under `tests/evals/` relevant to the change with `uv run pytest tests/evals/test_<name>.py`. Comment on the PR with the local evals actually run using the following template:

| Eval | Result |
| --- | --- |
| `<file or description>` | ✅ Passed / ❌ Failed |

If no eval applies, say so; do not run the full eval suite. Omit empty tables and never report an unrun check as passed.

5. Push and create or update the PR. Check mergeability and wait for hosted CI results. Fix failures before reporting success.
