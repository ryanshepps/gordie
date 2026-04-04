# Digest Flow

How scheduled digests are triggered, assembled, and delivered to users.

There are two digest types: **weekly digests** (Sunday mornings) and **news digests** (daily). Both follow the same trigger → filter → generate → deliver pipeline.

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        APScheduler (cron)                           │
│                                                                     │
│  Weekly: Sun 8:00 UTC          News: Daily 8:00 UTC                 │
└──────────┬──────────────────────────────┬───────────────────────────┘
           │                              │
           ▼                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Job Runner (per-user loop)                      │
│                                                                     │
│  1. Fetch all (user, league) pairs opted in for this digest type    │
│  2. Filter by subscription tier                                     │
│  3. For each eligible pair → run handler                            │
└──────────┬──────────────────────────────┬───────────────────────────┘
           │                              │
           ▼                              ▼
┌────────────────────────┐   ┌────────────────────────────────────────┐
│    Weekly Handler       │   │          News Handler                  │
│                         │   │                                        │
│  Yahoo API:             │   │  Fetch once (shared across users):     │
│  • Roster + last-week   │   │  • ESPN injuries                      │
│    stats                │   │  • NHL trades (RSS)                   │
│  • Current matchup      │   │  • Game-day matchups (NHL API)        │
│  • Hot free agents      │   │  • Teams playing today                │
│  • Schedule tips        │   │                                        │
│                         │   │  Per user:                             │
│  Assembles:             │   │  • Filter alerts by user's roster     │
│  DigestData model       │   │  • Analyze lineup decisions           │
│                         │   │  • Detect new injuries (vs saved      │
│                         │   │    state in DB)                       │
│                         │   │  • Skip if no relevant alerts         │
│                         │   │                                        │
│                         │   │  Assembles: NewsDigest model           │
└──────────┬──────────────┘   └──────────────────┬─────────────────────┘
           │                                     │
           ▼                                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Digest Writer (LLM)                            │
│                                                                     │
│  • GPT-4o-mini with persona + channel-specific guidelines           │
│  • Email: longer form (400-600 words), markdown                     │
│  • SMS: short (150-200 words), plain text                           │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Channel Resolver                                │
│                                                                     │
│  Has phone number AND not opted out of SMS?                         │
│  ┌─────────┐                    ┌──────────┐                        │
│  │   Yes   │───► SMS (Sinch)    │    No    │───► Email (Mailgun)    │
│  └─────────┘                    └──────────┘                        │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       Post-Delivery                                 │
│                                                                     │
│  • Save message_id for email thread continuity                      │
│  • Increment user's digest_count                                    │
│  • Save injury state snapshot (news digest only)                    │
│  • Log success/failure per user                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Trigger

APScheduler runs as a background thread alongside the server. Jobs are registered at startup in `scheduled/jobs.py`.

| Digest  | Schedule            | Handler                           |
|---------|---------------------|-----------------------------------|
| Weekly  | Sunday 8:00 AM UTC  | `scheduled/weekly_digest.py`      |
| News    | Daily 8:00 AM UTC   | `agent/news/send_news_digest.py`  |

Digests are not triggered by API endpoints. They run on schedule only.

## User Filtering

The job runner fetches all `(user_email, league_id)` pairs opted in for the digest type from `notification_preferences`. A user is opted in if they explicitly enabled the preference or if the notification type's default is enabled and they have no override.

Users on ineligible subscription tiers are skipped.

## Weekly Digest: Data Assembly

All data comes from the Yahoo Fantasy API, authenticated per user.

| Data                  | Source                           | What it provides                                              |
|-----------------------|----------------------------------|---------------------------------------------------------------|
| Roster performance    | Last week's stats                | Top 5 performers, bottom 3 underperformers, injured players   |
| Current matchup       | Yahoo matchup endpoint           | Opponent name and record                                      |
| Hot free agents       | Yahoo player search + stats API  | Top 5 available players with advanced stats (Corsi%, schedule) |
| Schedule tips         | NHL team schedule                | Teams with 4+ games (advantage) or 2- games (warning)         |

The handler assembles a `DigestData` model and passes it to the digest writer.

## News Digest: Data Assembly

Raw news is fetched once per job run, then filtered per user.

**Shared fetch (all users)**:
- **Injuries** from ESPN's public API
- **Trades** from NHL.com RSS feed (parsed via regex)
- **Game-day matchups** from NHL API — teams with high goals-against average
- **Teams playing today** from NHL daily schedule

**Per-user filtering** (`news_processor.py`):
- Matches alerts against the user's roster
- Enriches injury alerts with context: has game today, is new injury, already on IR slot
- Runs lineup analysis: benched players with games, position slot conflicts
- Compares current injuries against saved state in DB to detect new injuries
- Skips the digest entirely if no alerts are relevant to this user

## Content Generation

The digest writer sends the assembled data to GPT-4o-mini with a system prompt containing the bot persona and channel-specific guidelines.

| Channel | Weekly limit | News limit | Format     |
|---------|-------------|------------|------------|
| Email   | 600 words   | 400 words  | Markdown   |
| SMS     | 200 words   | 150 words  | Plain text |

News digests have additional prompt rules: suppress "tonight" when no game today, skip lineup advice when no conflicts exist, never append unsolicited questions.

## Delivery

**Channel resolution** checks the user record. If the user has a phone number and has not opted out of SMS, the digest goes via SMS. Otherwise, email.

**Email** (Mailgun):
1. Markdown converted to HTML with footer
2. Weekly digests enriched with inline player stat tables
3. Sent with both text and HTML bodies
4. Message ID saved for future thread continuity (replies route back to the agent)

**SMS** (Sinch):
1. Markdown stripped to plain text
2. Sent with retry logic (2 attempts, 2-second delay)

## Post-Delivery Tracking

After each successful send:
- `digest_count` incremented on the user's subscription record
- News digest saves current injury state snapshot to DB (used next run to detect new injuries)
- Job runner logs per-user success/failure and returns aggregate `JobResult` counts

## Key Files

| Area               | File                                        |
|--------------------|---------------------------------------------|
| Job registration   | `scheduled/jobs.py`                         |
| Job iteration      | `scheduled/job_runner.py`                   |
| Weekly digest      | `scheduled/weekly_digest.py`                |
| News orchestrator  | `agent/news/send_news_digest.py`            |
| News filtering     | `agent/news/news_processor.py`              |
| Lineup analysis    | `agent/news/lineup_analyzer.py`             |
| Content writer     | `agent/digest_writer.py`                    |
| Channel resolver   | `scheduled/channel_resolver.py`             |
| Email delivery     | `server/email_service.py`                   |
| SMS delivery       | `server/sms_service.py`                     |
| User preferences   | `data/notification_preference_repository.py` |
| Injury state       | `data/digest_injury_state_repository.py`    |
