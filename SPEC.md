# SPEC — Self-Hosted Billing Bypass

## §G — Goal

Gate all Creem/billing code behind presence of `CREEM_API_KEY`. When absent, server runs fully without billing surface. Self-hosters (AGPL-v3) never set Creem keys; only hosted deployment does.

---

## §C — Constraints

- C1. No separate branch or fork — single codebase, key-presence-gated.
- C2. No new env flag — `CREEM_API_KEY` presence is the signal.
- C3. Fail fast at startup (not at request time) when `CREEM_API_KEY` present but `CREEM_WEBHOOK_SECRET` absent (partial config).
- C4. No billing language in agent prompts when disabled.
- C5. Billing webhook endpoint must return 404 when disabled, not 500 or 200.
- C6. All existing billing behavior unchanged when all required Creem keys present.
- C7. All billing code lives under `billing/` top-level package — no billing logic scattered across `server/`, `agent/`, `data/`, or `tools/`.
- C8. Core modules access billing only via `billing.get_gateway()` — no direct imports of billing internals from outside `billing/`.

---

## §I — Interfaces

- I.env: `CREEM_API_KEY`, `CREEM_WEBHOOK_SECRET` env vars — presence determines billing mode
- I.supervisor: `agent/SupervisorAgent.py` — `tools` list passed to `create_agent`
- I.prompts: `agent/prompts/assemble.py` — `_build_context_section` billing branch
- I.routes: `billing/webhook.py` — `register_billing_routes(app)` (moved from `server/routes/webhook_routes.py`)
- I.server: `server/server.py` — startup, calls `billing.register_routes(app)` when enabled
- I.gateway: `billing/gateway.py` — `BillingGateway` Protocol, `NullBillingGateway`, `CreemBillingGateway`
- I.billing_pkg: `billing/__init__.py` — exports `billing_enabled: bool`, `get_gateway() -> BillingGateway`

---

## §V — Invariants

- V1. Billing enabled iff `CREEM_API_KEY` is set and non-empty. No other flag needed.
- V2. When disabled: `get_subscription_status`, `generate_checkout_link`, `generate_portal_link` not in supervisor tool list.
- V3. When disabled: `billing_blocked` branch in `_build_context_section` unreachable (billing context never injected).
- V4. When disabled: `GET/POST /webhooks/creem` returns HTTP 404.
- V5. When `CREEM_API_KEY` present but `CREEM_WEBHOOK_SECRET` absent: server raises `RuntimeError` before accepting connections.
- V6. Config read happens once at module import of `billing/__init__.py` — no scattered `os.getenv` calls for billing keys.
- V7. After reorganization, `grep` for imports of `server.creem_client`, `server.tier_enforcement`, `data.subscription_repository`, `tools.billing` in files outside `billing/` returns zero results.
- V8. `NullBillingGateway` satisfies `BillingGateway` Protocol with no Creem keys. All permission checks return `(True, "")`, `get_user_tier` returns `"free"`, tools list is empty.

---

## §T — Tasks

| id | status | description | cites |
|----|--------|-------------|-------|
| T1 | x | Create `billing/__init__.py`: infer `billing_enabled` from `CREEM_API_KEY`, export `get_gateway() -> BillingGateway`, `validate_billing_config()` | V1,V5,V6,I.env,I.billing_pkg |
| T2 | x | Create `billing/gateway.py`: `BillingGateway` Protocol, `NullBillingGateway` (all checks pass, tier=`"free"`), `CreemBillingGateway` (wraps `billing/tier.py`) | V8,I.gateway |
| T3 | x | Move files into `billing/`: `server/creem_client.py` → `billing/creem_client.py`, `server/tier_enforcement.py` → `billing/tier.py`, `server/routes/webhook_routes.py` → `billing/webhook.py`, `data/subscription_repository.py` → `billing/repository.py`, `tools/billing/` → `billing/tools/` | C7,V7 |
| T4 | x | `server/server.py`: call `validate_billing_config()` at startup; call `billing.register_routes(app)` only when enabled | V4,V5,I.server |
| T5 | x | `SupervisorAgent.py`: gate billing tools via `billing_enabled`; remove direct `tools.billing` imports (use `billing.tools.*`) | V2,V7,I.supervisor |
| T6 | x | `agent/prompts/assemble.py`: guard `billing_blocked` branch — skip when billing disabled | V3,I.prompts |
| T7 | x | Update remaining import sites: `server/routes/email_routes.py`, `server/routes/sms_routes.py`, `scheduled/jobs.py` — replace direct billing imports with `billing.get_gateway()` | V7,C8 |
| T8 | x | Update tests: fix import paths in `tests/unit/test_billing_tools.py`, `tests/unit/test_webhook_subscription_confirmation.py`, `tests/evals/test_supervisor_billing.py`, `tests/evals/test_tier_enforcement.py` | V7 |
| T9 | x | Unit tests: server starts and tools/routes correct with no Creem keys | V1,V2,V4 |
| T10 | x | Unit tests: `validate_billing_config()` raises on partial config (`CREEM_API_KEY` set, `CREEM_WEBHOOK_SECRET` missing) | V5 |
| T11 | x | Unit tests: `NullBillingGateway` satisfies Protocol; all checks return `(True, "")` | V8 |

---

## §B — Bugs

| id | date | cause | fix |
|----|------|-------|-----|
