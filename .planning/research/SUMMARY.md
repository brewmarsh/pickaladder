# Research Summary: pickaladder

**Domain:** Pickleball Ladder Systems
**Researched:** 2024-10-24 (Updated with Batch Recording)
**Overall confidence:** HIGH

## Executive Summary

The pickleball ecosystem is rapidly professionalizing, shifting from casual "open play" to structured competitive formats. The dominant force in this space is **DUPR (Dynamic Universal Pickleball Rating)**. 

A critical discovery in recent research is the high friction of match recording. Most users play **sessions** (multiple games with the same 4–8 people) rather than isolated matches. Current systems fail because they require a full "search-and-select" flow for every game. Transitioning to a **Session-First Workflow**—where a pool of players is selected once and games are logged with 2-3 taps—is a major differentiator for user retention and data accuracy.

## Key Findings

**Stack:** Python (Flask) with Firestore. Frontend needs robust local state for "Session" management and offline recording.
**Architecture:** Introduction of a **Session Entity** to group matches and pre-load player pools.
**Critical pitfall:** "Reporting Friction" leading to data abandonment. If it takes more than 15 seconds to log a game, users won't do it.

## Implications for Roadmap

Based on research, suggested phase structure:

1. **Phase 1: Session-First Core & Batch Recording** - Implement the "Session" container and a high-speed batch recording UI.
   - Addresses: The #1 user pain point (friction).
   - Features: Player pool selection, 2-tap score entry.

2. **Phase 2: Ranking & Movement Refinement** - Transition from "Average Score" to "ELO-First" sorting. Implement "Shootout" (Court Movement) logic.
   - Addresses: Competitive integrity.

3. **Phase 3: DUPR Integration** - Implement DUPR API sync for official rating validation.

4. **Phase 4: Automated Event Lifecycle** - Scheduling and full event management.

**Phase ordering rationale:**
- **UX First:** Solve the "Friction" problem (Phase 1) before perfecting the math (Phase 2). If users don't log matches because it's too hard, the best ELO algorithm in the world has no data to work with.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Core stack is well-suited. |
| Features | HIGH | Batch recording is a clear "missing link" in current apps. |
| Architecture | MEDIUM | Adding "Sessions" requires a schema update in Firestore. |
| Pitfalls | HIGH | Friction and data abandonment are well-documented. |

## Gaps to Address

- **Real-world DUPR API Access:** Still requires investigation into developer sandbox access.
- **Offline Sync Patterns:** Need a solid strategy for syncing multi-game sessions recorded in low-signal areas.
