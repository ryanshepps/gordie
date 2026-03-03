# Gordie Pricing Design

**Date:** 2026-02-06
**Status:** Approved

---

## Overview

Gordie is an AI-powered fantasy sports assistant that helps users make smarter decisions in their fantasy leagues. This document defines the pricing model, tier structure, and revenue projections for Gordie's launch and multi-sport expansion.

---

## Pricing Model: Reverse Trial + Freemium + Paid Tiers

### How It Works

1. **New user signs up** → gets 14 days of full, unrestricted access (no credit card required)
2. **After 14 days** → drops to free tier (3 questions/week, no digests or alerts)
3. **User can upgrade anytime** to Standard ($10/mo) or All-Star ($18/mo)

### Why Reverse Trial

The reverse trial model was chosen over pure freemium and pure free trial based on the following research:

- Reverse trials increase freemium-to-premium conversion by 10-40% compared to standard freemium ([Elena Verna, VP Growth at Dropbox — Amplitude blog](https://amplitude.com/blog/reverse-trial))
- Notion switched to a reverse trial and saw conversion rise from 17% to 25% ([Userpilot — Reverse Trial Method](https://userpilot.com/blog/saas-reverse-trial/))
- Non-converters stay on the free tier rather than leaving entirely, creating a "retention safety net" — Spotify reports 40-50% of churned Premium users re-subscribe within 3-12 months using this pattern ([Mack Collier — How Spotify Converts 40% of Free Users](https://mackcollier.substack.com/p/how-spotify-converts-40-of-free-users))
- 67% of freemium upgrades are triggered by hitting usage limits, not by wanting access to premium features ([Totango study — referenced in Userpilot](https://userpilot.com/blog/freemium-conversion-rate/))

### Why 14 Days

- 14 days covers ~2 weeks of a fantasy season — enough to experience a full weekly cycle (lineup decisions, waiver wire, trade analysis, a weekly digest)
- RevenueCat data across 10,000+ apps shows 7-day, 14-day, and 30-day trials convert at roughly the same median rate (~44-45%), so 14 days provides enough time without unnecessary delay ([RevenueCat — Trial Conversion Rate Insights](https://www.revenuecat.com/blog/growth/app-trial-conversion-rate-insights/))
- Products delivering core value within 24 hours convert 23% better with trials vs. freemium ([UserIntuition — Freemium vs Trial](https://www.userintuition.ai/reference-guides/freemium-vs-trial-what-research-says-about-conversion))

### Why 3 Questions/Week on Free Tier

- The free tier limit must be generous enough to maintain the habit but restrictive enough that engaged users hit the wall regularly
- 3 questions/week lets casual users ask "who should I start?" once but forces a choice between trade analysis, waiver wire, and lineup help in the same week
- Users who engage with core features within the first 7 days are 5x more likely to convert ([Mixpanel — referenced in ChartMogul data](https://userpilot.com/blog/freemium-conversion-rate/))
- Questions reset on Monday to align with the fantasy sports weekly cycle (Monday–Sunday)

---

## Tier Structure

### Free Tier (Post-Trial)

| Feature | Included |
|---|---|
| Ask Gordie questions | 3 per week (resets Monday) |
| Trade analysis | Yes (counts as a question) |
| Waiver wire recommendations | Yes (counts as a question) |
| Lineup help | Yes (counts as a question) |
| Weekly digest email | No |
| Daily news alerts | No |
| Conversation memory | Limited (last 7 days) |
| Sports supported | All available |
| Leagues supported | 1 |

### Standard Tier — $10/mo or $80/yr

| Feature | Included |
|---|---|
| Ask Gordie questions | Unlimited |
| Trade analysis | Unlimited |
| Waiver wire recommendations | Unlimited |
| Lineup help | Unlimited |
| Weekly digest email | Yes |
| Daily news alerts | Yes |
| Conversation memory | Full history |
| Sports supported | All available |
| Leagues supported | Up to 3 |

### All-Star Tier — $18/mo or $144/yr

| Feature | Included |
|---|---|
| Ask Gordie questions | Unlimited |
| Trade analysis | Unlimited |
| Waiver wire recommendations | Unlimited |
| Lineup help | Unlimited |
| Weekly digest email | Yes |
| Daily news alerts | Yes |
| Conversation memory | Full history |
| Sports supported | All available |
| Leagues supported | Unlimited |

### Tier Design Rationale

**Digests and alerts are paid-only.** These are "set and forget" features that deliver value passively. They're the stickiest features — once someone gets used to a Sunday morning digest, they won't cancel. Keeping them paid-only also means free users don't cost scheduled compute.

**Conversation memory is limited on free (7 days).** Free users lose context between weeks. Paid users get the "Gordie knows my team" experience that makes the assistant feel personal.

**3-league cap on Standard, unlimited on All-Star.** Each league adds real cost (Yahoo API calls, sub-agent chains per question, digest/alert compute). A power user in 10 leagues could cost $15-20/mo in OpenAI costs alone. Most fantasy players are in 1-3 leagues per sport ([FSGA Industry Demographics](https://thefsga.org/industry-demographics/)), so the 3-league cap only affects power users. The 80% price jump ($10 → $18) is justified because a 10-league user costs roughly 3-4x what a 1-league user costs.

**Annual billing discount (33% off).** Annual billing discounts of 33-50% are standard across the industry ([FantasyFootball.AI](https://www.fantasyfootball.ai/), [FantasyPros](https://www.fantasypros.com/premium/plans/)). Annual subscribers have near-zero churn and provide cash upfront.

---

## Competitive Landscape

### Fantasy Hockey Tools (Direct Competitors)

| Tool | Price | Model | AI-Powered |
|---|---|---|---|
| Hashtag Hockey | $2-2.50/mo | Patreon | No |
| Frozen Tools | $3-5/mo | Patreon | No |
| LeftWingLock | $7.99/yr | Annual | No |
| Dobber Hockey | $16-49/yr | Annual tiers | No |
| DailyFaceoff | Free | Ad-supported | No |

Sources: [Hashtag Hockey](https://hashtaghockey.com/), [Frozen Tools Patreon](https://www.patreon.com/frozentools), [LeftWingLock Season Pass](https://leftwinglock.com/seasonpass/), [DobberSports Shop](https://dobbersports.com/shop/), [DailyFaceoff](https://www.dailyfaceoff.com/)

### AI Fantasy Assistants (True Comp Set)

| Tool | Price | Sport | Notes |
|---|---|---|---|
| FantasyFootball.AI ("Jordy") | $6-15/mo | Football | Closest comp — AI chatbot with credit-based free tier (3 free/week) |
| NFL Fantasy AI (AWS) | $15/mo (bundled in NFL+ Premium) | Football | Inside NFL+ Premium |
| FantasySP AI Expert | $11/mo | Multi-sport | AI chatbot + tools |
| FantasyPros HOF | $9-12/mo | Multi (not hockey) | Trade analyzer, waiver assistant |

Sources: [FantasyFootball.AI](https://www.fantasyfootball.ai/), [NFL Fantasy AI Assistant](https://support.nfl.com/hc/en-us/articles/42933830263316-What-is-Fantasy-AI-Assistant-powered-by-AWS), [FantasySP Memberships](https://www.fantasysp.com/memberships/), [FantasyPros Plans](https://www.fantasypros.com/premium/plans/)

### Adjacent AI Assistant Pricing

| Service | Price | Notes |
|---|---|---|
| ChatGPT Plus | $20/mo | General-purpose AI |
| Claude Pro | $20/mo | General-purpose AI |
| Perplexity Pro | $20/mo | AI search |
| Google Gemini Advanced | $19.99/mo | General-purpose AI |

Sources: [ChatGPT Pricing](https://chatgpt.com/pricing), [AI Price Comparison 2026](https://www.sentisight.ai/ai-price-comparison-gemini-chatgpt-claude-grok/)

### Gordie's Positioning

Gordie at $10/mo sits in the middle of the AI fantasy assistant range ($6-15/mo), well below general-purpose AI assistants ($20/mo), and significantly above static hockey tools ($2-8/mo). This reflects the product's unique value: a conversational AI agent with live data integration, sub-agents for trade/waiver analysis, and personalized digests — capabilities none of the static hockey tools offer.

---

## Market Context

### Fantasy Hockey Market Size

- 4-7 million fantasy hockey players in US and Canada, derived from ~57 million total fantasy sports participants ([FSGA 2025 Research](https://thefsga.org/fsgas-2025-research-fantasy-sports-womens-betting-social-sportsbooks/)) with hockey representing ~12% of participants ([FSGA Industry Demographics](https://thefsga.org/industry-demographics/))
- Fantasy hockey is the fastest-growing fantasy segment at 14.6% CAGR ([Business Research Insights — Fantasy Sports Market](https://www.businessresearchinsights.com/market-reports/fantasy-sports-market-106528))
- ~20% of fantasy players pay for premium tools ([JPLoft — How Fantasy Sports Apps Make Money](https://www.jploft.com/blog/how-fantasy-sports-apps-make-money))
- Average tool spend: $120-180/year (~$10-15/mo) ([FSGA — Per-Player Spending](https://thefsga.org/fantasy-sports-participation-per-player-spending-continue-to-rise/))
- 60% of fantasy players pay for some form of premium content ([PRNewswire — Era of Immersive Sports](https://www.prnewswire.com/news-releases/game-changing-generational-trends-and-shifts-in-tech-lead-to-the-era-of-immersive-sports-301863219.html))

### Multi-Sport Expansion

Fantasy football represents ~79% of fantasy participants (~45M users) vs. hockey's ~12% (~6.8M). Adding football expands the total addressable market by roughly 7-10x. Basketball (32%, ~18M) and baseball (22%, ~12.5M) provide additional growth vectors.

Source: [FSGA Industry Research](https://thefsga.org/industry-research/)

---

## Conversion Rate Assumptions

| Metric | Conservative | Optimistic | Source |
|---|---|---|---|
| Trial → paid (within 14 days) | 12% | 18% | Opt-in trial benchmark: 18-25% ([Lenny Rachitsky](https://www.lennysnewsletter.com/p/what-is-a-good-free-to-paid-conversion)); reverse trial uplift of 10-40% over standard freemium ([Amplitude/Elena Verna](https://amplitude.com/blog/reverse-trial)); discounted slightly for seasonal sports product |
| Free tier → paid (within 90 days post-trial) | 5% | 8% | Freemium self-serve: 3-5% good, 6-8% great ([Lenny Rachitsky/OpenView/Pendo](https://www.lennysnewsletter.com/p/what-is-a-good-free-to-paid-conversion)); niche enthusiast audiences skew higher; 67% of upgrades triggered by usage limits ([Totango](https://userpilot.com/blog/freemium-conversion-rate/)) |
| Combined effective conversion | 16% | 24% | Calculated: trial conversion + (remaining non-converters × free-to-paid rate) |
| Monthly churn (paid users) | 6% | 4% | Consumer SaaS at $5-15/mo: 6.1% monthly churn ([Recurly — Churn Rate Benchmarks](https://recurly.com/research/churn-rate-benchmarks/)); niche engaged audiences trend lower |
| Standard / All-Star split (hockey only) | 75% / 25% | — | Estimated: most hockey users are in 1-3 leagues |
| Standard / All-Star split (multi-sport) | 65% / 35% | — | Estimated: multi-sport users more likely to exceed 3 leagues |

---

## Cost Assumptions

| Cost | Amount | Rationale |
|---|---|---|
| OpenAI cost per free user/mo | ~$0.50 | GPT-4o-mini at $0.15/1M input tokens, $0.60/1M output tokens; 3 questions/week with sub-agent chains averaging ~4K tokens per question |
| OpenAI cost per paid user/mo | ~$2.00 | Heavier usage (unlimited questions, averaging ~15-20 questions/week); plus digest and alert generation compute |
| Infrastructure (Mac Mini + Cloudflare) | ~$50/mo | Fixed cost; Mac Mini is owned hardware, Cloudflare Workers free tier covers frontend |
| Mailgun | ~$0.80/1000 emails | Transactional email costs scale with user base |
| Yahoo API | $0 | Free for non-commercial use under Yahoo Fantasy API terms |
| MoneyPuck | $0 | Free, non-commercial NHL stats |

---

## 18-Month Revenue Projection

### Signup Assumptions

| Phase | Monthly Signups | Rationale |
|---|---|---|
| Months 1-9 (hockey only) | 150/mo | Conservative for niche launch; organic + initial marketing |
| Months 10-18 (multi-sport) | 400/mo | Football expands TAM ~7-10x; increased marketing spend |

### Paid User Growth Model

Paid users in any given month = (previous month's paid users × (1 - churn rate)) + new conversions from trial + new conversions from free tier.

Using conservative estimates (12% trial conversion, 5% free-to-paid, 6% monthly churn):

### Projection Table

| Phase | Free Users (cumulative) | Paid Users (net of churn) | Blended ARPU | MRR | Monthly OpenAI + Infra Cost |
|---|---|---|---|---|---|
| Month 3 | 350 | 85 | $12.00 | $1,020 | $275 |
| Month 6 | 700 | 210 | $12.00 | $2,520 | $550 |
| Month 9 | 1,050 | 370 | $12.00 | $4,440 | $825 |
| Month 12 (football live) | 1,950 | 620 | $12.80 | $7,935 | $1,375 |
| Month 18 | 3,750 | 1,200 | $12.80 | $15,360 | $2,375 |

**Blended ARPU calculation:**
- Hockey-only (months 1-9): 75% Standard × $10 + 25% All-Star × $18 = **$12.00**
- Multi-sport (months 10-18): 65% Standard × $10 + 35% All-Star × $18 = **$12.80**

### Summary

| Metric | 18-Month Total |
|---|---|
| Total revenue | ~$105,000 |
| Total costs (OpenAI + infra) | ~$25,000 |
| **Net revenue** | **~$80,000** |
| Paid users at month 18 | ~1,200 |
| Free users in ecosystem | ~3,750 |
| MRR at month 18 | ~$15,360 |

### Key Inflection Points

- **Month 5-6:** Cross ~$2,000 MRR — covers infrastructure costs comfortably
- **Month 9-10:** Football launches; signup velocity jumps; All-Star tier adoption increases as multi-sport users arrive
- **Month 15-18:** Compounding kicks in; free user base generates organic signups; MRR approaching $15K

---

## Risk Factors

| Risk | Mitigation |
|---|---|
| OpenAI cost increases | GPT-4o-mini is already cheap; can switch to open-source models if costs spike |
| Seasonal churn (hockey offseason) | Multi-sport expansion fills the gap; football draft season starts as hockey ends |
| Low trial conversion (<10%) | Optimize onboarding flow; ensure users experience trade analysis + digest during trial |
| Free tier too generous | Monitor usage; can reduce from 3 to 2 questions/week if conversion is low |
| Power users on All-Star costing too much | Monitor per-user cost; can add soft usage limits if needed |
| Yahoo API changes/deprecation | ESPN and Fantrax integrations planned as alternatives |

---

## Future Pricing Considerations

- **Add sports without raising prices.** Each new sport increases the value proposition for existing subscribers, improving retention and reducing churn. This is the primary advantage of pricing for the platform vision now.
- **Potential Pro/Enterprise tier.** If demand emerges for commissioner tools, league-wide analysis, or API access, a higher tier ($25-30/mo) could be introduced.
- **Seasonal billing option.** A 6-month seasonal pass (e.g., $50 for a hockey season) could reduce commitment anxiety for users who only play one sport.
