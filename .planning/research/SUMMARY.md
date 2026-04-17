# Research Summary: pickaladder

**Domain:** Pickleball Ladder Systems
**Researched:** 2025-05-24
**Overall confidence:** HIGH

## Executive Summary

The pickleball ecosystem is rapidly professionalizing, shifting from casual "open play" to structured competitive formats. The dominant force in this space is **DUPR (Dynamic Universal Pickleball Rating)**, which has become the de facto standard for skill assessment. 

Competitive platforms now focus on two primary value drivers: **Fairness** (accurate ratings/matchmaking) and **Convenience** (automated scheduling/reporting). Most modern systems utilize either a continuous **ELO-based ranking** or a session-based **"Shootout" (Step) algorithm** where players move between courts based on immediate performance.

For `pickaladder`, the current implementation provides a solid foundation with ELO calculations and basic leaderboard logic, but there is a clear opportunity to move from "Average Score" sorting to a more sophisticated rating-driven leaderboard and eventually integrate official DUPR data.

## Key Findings

**Stack:** Python (Flask) with Firestore. Integration with DUPR API is the primary growth vector.
**Architecture:** Service-oriented approach for match processing and leaderboard generation.
**Critical pitfall:** Stagnation in ELO systems where top players stop playing to "protect" their rank, solved by "Leap-Frog" or activity requirements.

## Implications for Roadmap

Based on research, suggested phase structure:

1. **Phase 1: Ranking & Movement Refinement** - Transition from "Average Score" to "ELO-First" sorting. Implement "Shootout" (Court Movement) logic for groups.
   - Addresses: Table stakes competitive expectations.
   - Avoids: Misleading rankings based on volume vs skill.

2. **Phase 2: DUPR Integration** - Implement DUPR API sync to allow users to verify their "Official" rating within the app.
   - Addresses: Market demand for DUPR-verified matches.
   - Rationale: High value for competitive players.

3. **Phase 3: Automated Event Lifecycle** - From scheduling to court assignments to final reporting.
   - Addresses: Organizer burnout (the #1 reason ladders fail).

**Phase ordering rationale:**
- Establish internal rating integrity first (Phase 1) before connecting to external systems (Phase 2). Scaling to full event management (Phase 3) requires a robust core.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Core stack is well-suited for current needs. |
| Features | HIGH | Table stakes are well-defined in the market. |
| Architecture | MEDIUM | Current leaderboard logic is coupled with Firestore streams; may need optimization for scale. |
| Pitfalls | HIGH | Common issues like sandbagging and inactivity are well-documented. |

## Gaps to Address

- **Real-world DUPR API Access:** Requires "Club" status or partnership; needs investigation into developer sandbox access for the current project.
- **Mobile Push Notifications:** Essential for "Flex" ladders (matches scheduled by players) to ensure timely reporting.
