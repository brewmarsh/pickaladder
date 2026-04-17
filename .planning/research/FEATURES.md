# Feature Landscape

**Domain:** Pickleball Ladder Systems
**Researched:** 2025-05-24

## Table Stakes

Features users expect in any pickleball ladder app.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| ELO/Rating Ranking | Users want to see where they stand against others accurately. | Medium | Current system has ELO code but leaderboard uses Avg Score. |
| Score Reporting | Direct entry of match results after play. | Low | Core functionality. |
| Double/Singles Support | Pickleball is predominantly played as doubles. | Medium | Handling partner pairings and rating updates. |
| Leaderboards | Visual ranking of group members. | Low | Already exists in basic form. |
| Match Verification | Prevention of "fake" wins by requiring opponent approval. | Medium | Critical for competitive integrity. |

## Differentiators

Features that set `pickaladder` apart.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| DUPR Sync | Official rating validation directly in the app. | High | Requires Partner API access. |
| Shootout Automation | Handles "4-player" and "5-player" court movement automatically. | High | Unique to pickleball "round robin" social play. |
| "On Fire" Badges | Gamification of winning streaks. | Low | Already implemented in current codebase. |
| Ghost Management | Allowing organizers to handle "filler" players without breaking stats. | Medium | Essential for odd-numbered groups. |
| Flex Ladder Scheduling | Propose/Accept match workflow for unscheduled play. | High | Significant UX complexity. |

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Manual Ranking Overrides | Leads to accusations of bias or "playing favorites." | Use pure algorithm-based rankings with clear tiebreakers. |
| In-App Messaging (Full) | High maintenance/moderation overhead. | Use integration with WhatsApp/SMS or simple match comments. |

## Feature Dependencies

```
Match Reporting → ELO Calculation → Leaderboard Display
DUPR API Integration → Verified Rating Badge → Verified-Only Matches
Group Management → Shootout Logic → Court Assignments
```

## MVP Recommendation

Prioritize:
1. **ELO-Based Leaderboard:** Switch primary sorting from `avg_score` to `elo`.
2. **Score Verification:** Add a "Pending Verification" state to matches.
3. **Basic Shootout Support:** A tool to generate court assignments for 4/5 player pools.

Defer: **Full DUPR Sync** (until Partner API access is secured).

## Sources

- [Global Pickleball Network Features](https://www.globalpickleball.network/)
- [PlayTime Scheduler Patterns](https://playtimescheduler.com/)
