# Tests

Three suites:

| Suite | Path | Needs | Speed |
|-------|------|-------|-------|
| Unit | `tests/unit/` | nothing | fast |
| Integration | `tests/integration/` | live Yahoo, Postgres, possibly LLM | slow |
| Eval | `tests/evals/` | Postgres (sometimes), mocks the LLM | medium |

## Run

```bash
uv run pytest tests/unit                         # always safe
uv run pytest tests/evals/test_<file>.py         # one eval at a time
uv run pytest -m "not integration"               # skip live-API tests
uv run pytest                                    # everything (slow)
```

## Eval suite notes

Evals mock `ChatOpenAI` and friends — they do not consume real LLM tokens. They DO load `.env` via dotenv, so an unset `OPENAI_API_KEY` may surface in unrelated module init paths. Easiest fix: keep a placeholder `OPENAI_API_KEY=test` in your test env.

The full eval run takes 5+ minutes. Cherry-pick when iterating.

## Coverage

```bash
uv run pytest --cov=. --cov-report=html
open htmlcov/index.html
```

## What tests cover

- `tests/unit/` — pure-function logic, schema validation, prompt assembly, channel resolution
- `tests/evals/` — agent routing decisions (which sub-agent / which tool), notification triage, digest content, data quality
- `tests/integration/` — real Yahoo OAuth flow, SMS round trips, webhook signature verification
