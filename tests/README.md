# Tests

Run Python commands with `uv`.

```bash
uv run pytest tests/ --ignore=tests/evals
uv run pytest tests/evals/test_news_digest_filtering.py
uv run ruff check .
uv run ruff format --check .
```

The full eval suite is slow and may use an external model. Run only evals relevant to the changed behavior.
