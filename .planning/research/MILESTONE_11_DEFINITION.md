# Milestone 11: Market Readiness & Social Growth - Research

**Date:** 2026-04-28
**Status:** DRAFT
**Goal:** Define the scope for Milestone 11, focusing on features that will drive user adoption, social sharing, and ensure the platform can handle launch-day traffic.

## 1. Domain Research: Social Competition Growth
- **Referral Systems**: Successful sports apps (like DUPR) grow by making it easy for users to invite their "court-mates".
- **Social Sharing**: "Brag Cards" are great, but they need to be shareable as images with Open Graph meta tags for platforms like Twitter and iMessage.
- **Viral Loops**: Rewarding users (with Social Credits) for successful referrals and completed matches.

## 2. Technical Research: Bottlenecks & Efficiency
- **Asynchronous Tasks**: Currently, emails are sent synchronously. This will slow down requests in production. We need a background task solution (e.g., Celery, or a simplified ThreadPoolExecutor for lightweight needs).
- **Caching Strategy**: The Global Leaderboard and Division Hubs are read-heavy. Implementing a cache (Redis or similar) will significantly reduce Firestore read costs.
- **Health Monitoring**: We need a `/health` endpoint and better uptime monitoring for the production environment.

## 3. Proposed Phases for Milestone 11

### Phase 24: Asynchronous Processing & Reliability
**Goal:** Move long-running tasks to the background and improve system resilience.
- Implement a background task manager for email and push notifications.
- Add a robust health check system.
- Finalize the automated backup strategy for Firestore.

### Phase 25: High-Performance Data Access (Caching)
**Goal:** Optimize read-heavy endpoints to reduce latency and cost.
- Implement a caching layer for Global and Group leaderboards.
- Add cache-invalidation logic on match recording.
- Optimize asset delivery (CDN-ready paths).

### Phase 26: Viral Growth & Launch Prep
**Goal:** Finalize the user-facing polish for launch day.
- Enhance the Referral System with Social Credit rewards.
- Implement Open Graph (OG) meta tags for dynamic social sharing (Brag Cards).
- Create a "Welcome" onboarding flow for new users coming from referral links.

## 4. Success Criteria
- [ ] Email sending does not block the request-response cycle.
- [ ] Global Leaderboard load time < 200ms (cached).
- [ ] Brag Cards display correctly when shared on social media.
- [ ] Referral flow verified from link click to reward payout.

## 5. Next Steps
- Finalize this research.
- Update `ROADMAP.md` and `STATE.md` with Milestone 11 details.
- Create Phase 24 Plan.
