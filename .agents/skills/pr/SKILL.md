---
name: pr
description: Create or update a verified pull request for Gordie, run targeted evals, and comment the actual results. Use when asked to create, open, update or ship a PR.
---

# PR

1. Fetch the latest default branch and merge it into the working branch. Stop for non-trivial conflicts.
2. Review the diff, stage only intentional files, and commit using the repository's commit style.
3. Run evals that are relevant to the cahnge with `uv run pytest tests/evals/test_<name>.py`. Note the evals you ran in the PR body using the following template:

| Eval | Result |
| --- | --- |
| `<name>` | ✅ Passed / ❌ Failed |

For evals, only add the table.

4. Push and create or update the PR. Check mergeability and wait for hosted CI results. Fix failures before reporting success. If new evals are ran, update the PR body with the new results.
