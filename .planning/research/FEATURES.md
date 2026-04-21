# Feature Landscape

**Domain:** Pickleball Ladder Systems
**Researched:** 2024-10-24 (Updated with Batch Recording)

## Table Stakes

Features users expect in any pickleball ladder app.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| ELO/Rating Ranking | Users want to see where they stand against others accurately. | Medium | Current system has ELO code but leaderboard uses Avg Score. |
| Score Reporting | Direct entry of match results after play. | Low | Core functionality. |
| **Batch Match Recording** | **Users play 3+ games per session; recording them individually is too slow.** | **Medium** | **Critical for user retention.** |
| Double/Singles Support | Pickleball is predominantly played as doubles. | Medium | Handling partner pairings and rating updates. |
| Leaderboards | Visual ranking of group members. | Low | Already exists in basic form. |
| Match Verification | Prevention of "fake" wins by requiring opponent approval. | Medium | Critical for competitive integrity. |

## Differentiators

Features that set `pickaladder` apart.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Session-First Workflow** | **Pre-select a pool of 4-8 players and log a whole session in seconds.** | **Medium** | **Reduces friction by 80% compared to DUPR.** |
| DUPR Sync | Official rating validation directly in the app. | High | Requires Partner API access. |
| Shootout Automation | Handles "4-player" and "5-player" court movement automatically. | High | Unique to pickleball "round robin" social play. |
| "On Fire" Badges | Gamification of winning streaks. | Low | Already implemented in current codebase. |
| Ghost Management | Allowing organizers to handle "filler" players without breaking stats. | Medium | Essential for odd-numbered groups. |

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Manual Ranking Overrides | Leads to accusations of bias or "playing favorites." | Use pure algorithm-based rankings with clear tiebreakers. |
| In-App Messaging (Full) | High maintenance/moderation overhead. | Use integration with WhatsApp/SMS or simple match comments. |

## Feature Dependencies

```
Session Pool Selection → Batch Match Entry → ELO Calculation → Leaderboard
Match Reporting → ELO Calculation → Leaderboard Display
DUPR API Integration → Verified Rating Badge → Verified-Only Matches
Group Management → Shootout Logic → Court Assignments
```

## MVP Recommendation

Prioritize:
1. **Batch Recording UI:** Use a "Session" concept to log multiple games from a single pool of players.
2. **ELO-Based Leaderboard:** Switch primary sorting from `avg_score` to `elo`.
3. **Score Verification:** Add a "Pending Verification" state to matches.

Defer: **Full DUPR Sync** (until Partner API access is secured).

## Sources

- [Global Pickleball Network Features](https://www.globalpickleball.network/)
- [PlayTime Scheduler Patterns](https://playtimescheduler.com/)
- [Research: Batch Recording Workflows](./BATCH_RECORDING.md)
