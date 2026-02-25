# Inbound Message Flow

How user messages reach Gordie and how Gordie responds, from webhook to delivery.

## Entry Points

Two webhooks accept inbound messages. Both return HTTP 200 immediately and process the message in a background thread.

| Channel | Endpoint | Provider | Route File |
|---------|----------|----------|------------|
| Email | `POST /email/webhook` | Mailgun | `server/routes/email_routes.py` |
| SMS | `POST /sms/webhook` | Sinch | `server/routes/sms_routes.py` |

## Webhook Validation

Both webhooks run the same guard sequence before processing:

1. **Signature verification** — HMAC check against the provider's secret (Mailgun token+timestamp+signature; Sinch raw body + `X-Sinch-Signature` header)
2. **Idempotency** — the provider's message ID is checked against `processed_emails` / `processed_sms` tables to prevent duplicate processing
3. **SMS-only: rate limiting** — in-memory sliding window (5 messages per 60 seconds per phone number)
4. **SMS-only: opt-out/opt-in** — STOP/START keywords are handled inline and short-circuit before reaching the agent
5. **SMS-only: cold start** — if the phone number has no registered user, an OAuth link is sent instead of invoking the agent

## Thread Resolution

Each channel resolves a `thread_id` to maintain conversation continuity. See `server/thread_manager.py`.

**Email** uses RFC 5322 headers:

1. Check `In-Reply-To` header against `email_threads` table
2. Fall back to `References` header
3. If neither matches, create a new thread (`{email}:{uuid}`)

**SMS** maps each phone number to exactly one permanent thread. If a thread exists for the phone number, it is reused. Otherwise a new thread is created. Thread format: `sms:{phone}:{uuid}`.

## Agent Processing

After thread resolution, both channels call `message_agent()` in `scripts/message_agent.py`. This function:

1. Persists the user message to the `conversation_messages` table
2. Builds initial `AgentState` (user email, thread ID, channel, message)
3. Invokes the LangGraph agent

The graph has two nodes executed sequentially: **supervisor** → **response**.

### Supervisor Node

The supervisor (`agent/SupervisorAgent.py`) is an LLM agent (GPT-4o-mini) with tool-calling capabilities. On each invocation it:

1. Runs **context validation** — determines the user's teams, league context, and onboarding status. Builds a system message with this context.
2. Prepends **persona** and **context** system messages to the conversation
3. Invokes the LLM, which can call tools: `trade`, `available_players`, `onboard_user_team`, `search_past_conversations`, `manage_notifications`, and (SMS-only) `send_acknowledgement`
4. Extracts the final AI response and routes to the **response** node

> **SMS acknowledgement**: On the SMS channel, the supervisor has access to `send_acknowledgement`, which sends a short "working on it" SMS before executing longer tool calls. This prevents the user from waiting in silence.

### Response Node

The response node (`agent/response_node.py`) dispatches the supervisor's response to the user and stores a conversation summary in the memory store.

**Email dispatch** (`agent/channels/email_channel.py`):

1. Determines the subject line (preserves `Re:` threading from the original)
2. Enriches the response with an HTML player statistics table if players were mentioned
3. Formats the email (text + HTML with footer)
4. Sends via Mailgun
5. Saves the outbound `Message-ID` → `thread_id` mapping so future replies thread correctly

**SMS dispatch**:

1. Extracts the phone number from the thread ID
2. Sends the response as a single SMS via Sinch

After dispatch, `message_agent()` persists the AI response to the `conversation_messages` table.

## Sequence Overview

```
User sends SMS/Email
        │
        ▼
  Webhook handler
  (verify signature, deduplicate)
        │
        ├── SMS-only: rate limit, opt-out, cold-start checks
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
                     ┌─── LangGraph ───┐
                     │                 │
                     │   Supervisor    │
                     │   (LLM + tools) │
                     │        │        │
                     │        ▼        │
                     │    Response     │
                     │   (dispatch)    │
                     │                 │
                     └─────────────────┘
                              │
                              ▼
                    Send email (Mailgun)
                    or SMS (Sinch)
                              │
                              ▼
                    Persist AI response
```
