# Fantasy Agent

## 1.0 Roadmap

### Agents

- [x] Email correspondence.
- [ ] Trade Agent
  - [ ] Makes consistent recommendations.
  - [ ] Good recommendations.
  - [ ] Finds teams that are desperate for the subject player (e.g., Team 4 is desperate for Quarterback)
- [ ] Waiver Agent
  - [ ] Makes consistent recommendations.
  - [ ] Good recommendations.
- [ ] Player Comparison Agent (When trades/waivers don't apply; e.g, dropping a player on your roster for a player who has become healthy on IR)
- [ ] Weekly Agent
  - [ ] Emails player weekly with lineup recommendations.
  - [ ] Analyzes opponent's lineup and gives strategy recommendations.
  - [ ] Schedule based streams/optimizations.
- [ ] News Agent
  - [ ] Game-day alerts (x is facing a weak team today. You should start them)
  - [ ] Injury wire monitoring
  - [ ] Real-world trade monitoring (e.g., player just got traded, you should pick them up because they can potentially do better)
  - [ ] Line promotion/demotion alerts.
- [ ] Conversation management.
  - [ ] Can read user's previous conversations.
  - [ ] Pulls in appropriate team context automatically and asks for clarification when it can't determine the user's team given the context.
- [ ] Add personalized tips at the end of each email.
- [x] Add table of player stats for all users mentioned in message at end of email.

### Infrastructure

- [x] Fetch advanced stats.
- [ ] Deployed onto Mac Mini.
- [ ] Grafana for logging user errors.
- [ ] Consistently fetches and updates player data.
- [ ] Database backups.
- [ ] Save learnings so that the agent can automatically improve.

### UX

- [x] Yahoo onboarding.
  - [ ] Onboard single team.
  - [ ] Onboard multiple leagues.
  - [ ] Onboard multiple sports.
- [ ] Pay for each team using Stripe.

## Future features

### UX

- [ ] ESPN onboarding
- [ ] Fantrax onboarding
- [ ] CBS onboarding
- [ ] Referral system