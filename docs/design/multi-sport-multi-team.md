# Multi-Sport / Multi-Team Communication Design

## Overview

Gordie expands from a hockey-only assistant to a multi-sport, multi-team assistant. One Gordie, one phone number, one email — but with sport-adaptive voice and smart context resolution to handle users who have many teams across many sports.

## Communication Channels

### SMS (primary conversational channel)

- Single phone number for all sports.
- Smart context inference resolves which team the user is talking about (see Context Resolution below).
- Single-team users experience zero friction.

### Email (async, per-league threads)

- Each league gets its own email thread via subject-line threading.
- Rich HTML formatting for detailed analysis, stat tables, trade breakdowns.
- Extended to all sports — unchanged architecture.

### Web Chat (future)

- Not built now.
- When ready, use a managed auth provider (Clerk, Auth0) to avoid building security infrastructure.
- Per-league threads in a sidebar, real-time responses.
- SMS can drive users to it: "I put together a full breakdown — check it out at gordie.app/chat"

## Multi-Team Context Resolution

When a user sends a message over SMS, Gordie resolves which team they're talking about by running through these steps in order:

1. **Explicit reference** — User says "in my Kraken league" or "on my dynasty team" → resolved immediately.
2. **Sport narrowing** — User mentions a baseball player or baseball concept → filter to baseball teams only. If there's only one baseball team, resolved.
3. **Player narrowing** — User mentions a specific player → check which of their teams has that player rostered or available in their league. If only one team matches, resolved.
4. **Conversational carry-forward** — If the user's recent messages were about a specific team, assume the conversation is still in that context until they signal otherwise.
5. **Ask** — If none of the above resolves it, Gordie asks. Short and casual: "Which league — your Avalanche one or the Kraken one?"

### Rules

- Gordie should have a low threshold for asking. Getting the wrong team is worse than a clarifying question.
- Once a team context is established in a conversation, it sticks until the user changes it or the conversation goes cold (6+ hours of no messages).
- Gordie should confirm context when it's not obvious: "Talking about your Kraken league — you should grab Beniers off waivers before tomorrow."

## Digests

- One digest per team, sent on the league's "week start" day (Monday for most leagues, Thursday for NFL, etc.).
- Delivered via the user's preferred channel (SMS or email).
- All digests for the same sport/day go out as separate messages, not merged.

### User Control

- Users can disable digests per team via conversation: "stop sending me digests for my Kraken league."
- Users can reschedule digests per team via conversation: "send my baseball digests on Tuesdays instead."
- No settings page needed — managed through conversation with Gordie.

### Content

- Each digest is contextual to that specific team and league — matchup preview, roster notes, hot free agents, schedule advantages.
- Gordie's voice adapts to the sport (hockey talks Corsi, baseball talks ERA) but it's still Gordie.

### Volume Monitoring

- If users with 5+ teams start disabling digests, that's a signal volume is too high. Revisit consolidated digests if this becomes a pattern.

## Gordie's Sport-Adaptive Voice

Gordie is one character who code-switches naturally depending on the sport.

### Core Personality (constant across all sports)

- Tough, direct, confident.
- Gives you the answer, not a hedge.
- Uses stats to back up opinions but doesn't lecture.
- Talks like a friend who watches too much sports, not a chatbot.
- Never says "as an AI" or breaks character.
- Never reveals tools, sub-agents, or system internals.

### Sport-Specific Adaptation

- **Hockey** — Grizzled scout. "His Corsi is elite but he's on the second line, so the ceiling is capped. Grab him if you need depth, don't overpay."
- **Baseball** — Sabermetrics-savvy but not preachy. "His xBA is way higher than his actual average — he's been unlucky. Buy low before your leaguemates notice."
- **Football** — Film room energy. "He's seeing 85% snap share and the target share is climbing. Lock him in."
- **Basketball** — Pickup game trash talk meets analytics. "He's averaging a triple-double in the last two weeks and nobody in your league is paying attention."

### Implementation

- Sport-specific persona prompts that layer on top of the core persona.
- Each sport gets its own stats vocabulary, reference points, and example phrasing.
- Core rules and behavioral guardrails are shared.

## Onboarding for Multi-Sport

### OAuth Flow

- Yahoo OAuth already grants access across all sports. When a user connects, Gordie discovers all their active fantasy teams across all sports.
- After OAuth, Gordie presents what he found: "I can see you've got 2 hockey leagues, 1 baseball league, and 1 football league. Want me to set up for all of them?"
- User can pick which teams to activate. Not every team needs Gordie's attention.

### New Leagues Mid-Season

- If the user joins a new league mid-season, Gordie discovers it on the next token refresh and asks: "Looks like you joined a new baseball league. Want me to cover that one too?"

### Single-Team Users

- Nothing changes. They connect, Gordie finds one team, auto-onboards it. Zero friction.

### Platform Expansion (ESPN, Sleeper, etc. — future)

- Each platform gets its own OAuth connection.
- Gordie can prompt: "Want to connect your ESPN leagues too?"
- Teams from different platforms are treated the same in conversation — the user doesn't need to think about which platform a team is on.
