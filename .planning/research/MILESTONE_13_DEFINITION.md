# Milestone 13: Global Scale & Ecosystem Integration - Research

**Date:** 2026-04-29
**Status:** DRAFT
**Goal:** Transition from a group-focused tool to a platform-scale ecosystem with cross-group comparisons, developer tools, and a monetization foundation.

## 1. Domain Research: Platform Ecosystems
- **Cross-Group Analytics**: Users want to know how they rank not just in their local club, but across the entire city or platform. This requires aggregating ELO/DUPR data globally.
- **Developer Accessibility**: Clubs often have their own websites or display boards. A public API or "Widget" system would allow pickaladder to be embedded elsewhere.
- **Sustainability**: Moving towards a SaaS model requires subscription management (Free vs. Pro) and payment processing.

## 2. Technical Research: Multi-Tenancy & APIs
- **Global Indexing**: Aggregating stats across 1000s of groups efficiently. We may need a specialized `global_stats` collection in Firestore.
- **OAuth2 / API Keys**: Securely allowing 3rd party access to user-authorized data.
- **Subscription Gates**: Implementing decorators or middle-ware that check a user's `tier` before allowing access to advanced features (like Pool Play or Advanced Analytics).

## 3. Proposed Phases for Milestone 13

### Phase 30: Global Statistics & Regional Rankings
**Goal:** Break the "Group Silo" and allow users to see their standing in the broader ecosystem.
- Implement a Global Leaderboard with regional filtering (City/State).
- Create "Global Player Cards" with historical ELO trends across all groups.
- Implement "Cross-Group Rivalries" (highlighting frequent opponents from different clubs).

### Phase 31: Developer API & External Integrations
**Goal:** Allow clubs and developers to build on top of pickaladder.
- Implement API Key management for users.
- Create a read-only REST API for fetching player stats and group rankings.
- Build an embeddable "Standings Widget" (HTML/JS snippet).

### Phase 32: Subscription Foundation & Premium Tier
**Goal:** Establish the infrastructure for platform monetization.
- Integrate Stripe (or a mock payment provider for MVP) for subscription handling.
- Implement user tiers: `basic` (Free) and `pro` (Subscription).
- Gate advanced features (e.g., unlimited active challenges, advanced pool play logic).

## 4. Success Criteria
- [ ] Global Leaderboard loads in < 300ms.
- [ ] API Key generated and successfully used to fetch a user's stats via `curl`.
- [ ] User tier successfully updated in Firestore and verified by a gated route.

## 5. Next Steps
- Finalize this research.
- Update `ROADMAP.md` and `STATE.md` with Milestone 13 details.
- Create Phase 30 Plan.
