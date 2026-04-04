# Inbound Message Flow

How user messages reach Gordie and how Gordie responds, from webhook to delivery.

## Entry Points

Two webhooks accept inbound messages. Both return HTTP 200 immediately and process the message in a background thread.

| Channel | Endpoint | Provider | Route File |
|---------|----------|----------|------------|
| Email | `POST /email/webhook` | Mailgun | `server/routes/email_routes.py` |
| SMS | `POST /sms/webhook` | Sinch | `server/routes/sms_routes.py` |

## Webhook Validation

Both webhooks run the same guard sequence before processing. Verification logic lives in `server/webhook_verification.py`.

1. **Signature verification** — Mailgun: HMAC-SHA256 over `{timestamp}{token}`; Sinch: Basic Authentication credentials checked against the `Authorization` header
2. **Timestamp freshness (email only)** — rejects webhooks older than 5 minutes to prevent replay attacks
3. **Idempotency** — the provider's message ID is checked against `processed_emails` / `processed_sms` tables to prevent duplicate processing
4. **SMS-only: rate limiting** — in-memory sliding window (5 messages per 60 seconds per phone number)
5. **SMS-only: opt-out/opt-in** — STOP/START keywords (and variants like UNSUBSCRIBE, CANCEL, END, QUIT) are handled inline and short-circuit before reaching the agent. Opted-out users receive no responses until they send START
6. **SMS-only: cold start** — if the phone number has no registered user, a pending user record is created and an OAuth link is sent via SMS instead of invoking the agent

## Billing Enforcement

Before invoking the agent, both channels check the user's subscription tier via `server/tier_enforcement.py`. If the user has exceeded their question limit, a `billing_context` string is built (including upgrade/checkout links via Creem) and passed into `message_agent()`. The context node detects this and short-circuits the agent into a billing-only response with no tool access.

## Thread Resolution

Each channel resolves a `thread_id` to maintain conversation continuity. See `server/thread_manager.py`.

**Email** uses RFC 5322 headers:

1. Check `In-Reply-To` header against `email_threads` table
2. Fall back to `References` header (tries each ref in order)
3. If neither matches, create a new thread (`{email}:{uuid}`)

**SMS** maps each phone number to exactly one permanent thread. If a thread exists for the phone number, its activity timestamp is updated and it is reused. Otherwise a new thread is created. Thread format: `sms:{phone}:{uuid}`.

## Agent Processing

After thread resolution, both channels call `message_agent()` in `scripts/message_agent.py`. This function:

1. Resolves the user's email (for SMS, looks up the user by phone number)
2. Persists the user message to the `conversation_messages` table
3. Builds initial `AgentState` with user email, thread ID, channel, message, and optional billing context
4. Invokes the LangGraph agent graph
5. Extracts the final AI response from the graph output
6. Persists the AI response to `conversation_messages`

## Agent Graph

The graph is defined in `agent/graph_builder.py` and has five nodes executed in sequence, with one feedback loop:

```
context → supervisor → data_quality → voice_rewrite → response → END
                ▲              │
                └──────────────┘
                  (retry with feedback, max 1)
```

### Context Node

The context node (`agent/context_node.py`) determines who the user is, what team they're asking about, and what sport applies. It returns a `context_status` that drives the rest of the flow.

1. **Billing block** — if `billing_context` is present, returns `billing_blocked` immediately
2. **OAuth check** — verifies the user has connected their Yahoo account. If not, generates an OAuth link and returns `first_time_user` or `no_oauth`
3. **Team resolution** — fetches onboarded teams from `YahooUserTeamRepository`. If no teams exist, triggers onboarding guidance
4. **Sport inference** — determines which sport the user is asking about using `agent/sport_inference.py`:
   - If the user has one team, that sport is used
   - Otherwise, infers from message keywords, team/league name matches, or a sticky 5-minute cache of the last inferred sport
   - If ambiguous, returns `team_ambiguous` so the supervisor can ask for clarification

Possible `context_status` values: `validated`, `first_time_user`, `no_oauth`, `no_teams_available`, `team_selection_needed`, `team_ambiguous`, `auto_onboarded`, `billing_blocked`, `error`.

### Supervisor Node

The supervisor (`agent/SupervisorAgent.py`) is a GPT-4o-mini agent with tool-calling capabilities. Three middleware layers wrap the model:

1. `StateLoggingMiddleware` — traces state for debugging
2. `sport_tool_filter` — filters tools to only those relevant to the inferred sport (e.g., NHL tools hidden when sport is MLB). Non-sport tools remain available regardless. Filtering rules live in `middleware/sport_tool_filter.py`
3. `handle_tool_errors` — wraps tool calls with error handling, retries, and metric tracking

The system prompt is assembled dynamically by `agent/prompts/assemble.py`, combining persona identity, behavioral rules, channel guidelines, context-specific instructions, and sport-specific stats definitions.

Available tools:

| Category | Tools |
|----------|-------|
| Sub-agents | `trade`, `available_players`, `statistician` |
| Data | `query_hockey_stats_db`, `query_mlb_stats_db` |
| Onboarding | `onboard_user_team` |
| Memory | `search_past_conversations` |
| Account | `manage_notifications`, `get_subscription_status`, `generate_checkout_link`, `generate_portal_link` |

If `context_status` is `billing_blocked`, the supervisor skips tool binding entirely and generates a billing-only response.

### Data Quality Node

The data quality node (`agent/data_quality_node.py`) validates the supervisor's response for statistical rigor. It checks whether players being compared or recommended have significantly different games-played counts, which would make raw stat comparisons misleading.

- If the check fails and retries remain (max 1), it sends feedback back to the supervisor for a revised response
- If the check passes or retries are exhausted, it routes to voice rewrite

### Voice Rewrite Node

The voice rewrite node (`agent/voice_rewrite_node.py`) rewrites the supervisor's response in Gordie's persona using GPT-4o-mini at temperature 0.5. It applies channel-specific formatting rules:

- **SMS**: max 600 characters, lead with the recommendation, cite 1-2 key stats only. If the rewrite exceeds 600 characters, a second pass condenses it
- **Email**: preserves structure, adjusts voice only

### Response Node

The response node (`agent/response_node.py`) dispatches the final message and stores a conversation summary.

**Email dispatch** (`agent/channels/email_channel.py`):

1. Determines the subject line (preserves `Re:` threading from the original, or generates one based on content)
2. Enriches the response with an HTML player statistics table if a league context is available
3. Formats the email (text + HTML with footer)
4. Sends via Mailgun
5. Saves the outbound `Message-ID` → `thread_id` mapping in `email_threads` so future replies thread correctly

**SMS dispatch** (`agent/channels/sms_channel.py`):

1. Extracts the phone number from the thread ID
2. Strips markdown from the response
3. Sends as a single SMS via Sinch
4. Updates thread activity timestamp

**Conversation memory** (`agent/memory_store.py`):

After dispatch, the response node calls `summarize_and_store_conversation()` which uses GPT-4o-mini to extract a summary, key topics, players mentioned, and decisions made from the last 10 messages. Summaries are stored in both:

- **LangGraph InMemoryStore** with OpenAI embeddings for semantic search (used by the `search_past_conversations` tool)
- **PostgreSQL** `conversation_summaries` table for durable storage

## Sequence Overview

```
User sends SMS/Email
        │
        ▼
  Webhook handler
  (verify signature, deduplicate, timestamp check)
        │
        ├── SMS-only: rate limit, opt-out, cold-start checks
        │
        ├── Billing tier enforcement
        │
        ▼
  Resolve thread_id
        │
        ▼
  Background thread ──► message_agent()
        │                     │
   Return 200                 ▼
   to provider          Persist user message
                              │
                              ▼
                     ┌─── LangGraph ────────────────────┐
                     │                                   │
                     │  1. Context                       │
                     │     (billing, OAuth, team, sport) │
                     │           │                       │
                     │           ▼                       │
                     │  2. Supervisor                    │
                     │     (LLM + sport-filtered tools)  │
                     │           │                       │
                     │           ▼                       │
                     │  3. Data Quality ──► retry? ──┐   │
                     │           │               back to │
                     │           ▼            Supervisor │
                     │  4. Voice Rewrite                 │
                     │     (persona + channel format)    │
                     │           │                       │
                     │           ▼                       │
                     │  5. Response                      │
                     │     (dispatch + memory)           │
                     │                                   │
                     └───────────────────────────────────┘
                              │
                              ▼
                    Send email (Mailgun)
                    or SMS (Sinch)
                              │
                              ▼
                    Persist AI response
                    Store conversation summary
```
