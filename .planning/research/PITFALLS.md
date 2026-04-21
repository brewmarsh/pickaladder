# Domain Pitfalls

**Domain:** Pickleball Ladder Systems
**Researched:** 2024-10-24 (Updated with Batch Recording)

## Critical Pitfalls

Mistakes that cause rewrites or major community issues.

### Pitfall 1: Rating Stagnation (The "Protecting Rank" Problem)
**What goes wrong:** High-ranked players stop playing to avoid risking their rank.
**Prevention:** Implement "Rank Decay" for inactivity or require minimum matches per period.

### Pitfall 2: Sandbagging
**What goes wrong:** High-skill players enter low-skill divisions to win easily.
**Prevention:** Force-sync with DUPR ratings where possible.

### Pitfall 3: **Reporting Friction (The "I'll Do It Later" Problem)**
**What goes wrong:** Users wait until the end of a 3-hour session to log 5 games, then forget the scores or players.
**Why it happens:** The app requires too many taps per game, so players don't want to do it between matches.
**Consequences:** Significant data loss and inaccurate leaderboards.
**Prevention:** Implement **Batch Recording** and **Session Management**. Allow one-tap "Repeat Players" for the next game.

## Moderate Pitfalls

### Pitfall 1: Forfeit Handling
**What goes wrong:** A player drops out mid-ladder, breaking the schedule for others.
**Prevention:** Automated "Sub" pool management.

### Pitfall 2: Match Reporting Disputes
**What goes wrong:** Player A reports a win, Player B reports a different score.
**Prevention:** Opponent must "Confirm" the score before it impacts ratings.

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| **Batch Recording** | **Users confuse "Team A" and "Team B" in bulk entry.** | **Use avatars/colors and a horizontal "Session Log" to show recent results.** |
| Ranking Migration | Resetting ELO to 1200 frustrates veterans. | Import legacy stats/avg scores as a "Starting Seed." |
| DUPR Sync | API Rate limits or stale data. | Cache DUPR ratings for 24 hours. |
| Shootout Logic | Handling "Ghost" players (odd numbers). | Pre-generate rotation maps for 3, 5, 7, 9... player counts. |

## Sources

- [Pickleball Community Discussions (Reddit/FB)](https://reddit.com/r/pickleball)
- [DUPR Integration Case Studies](https://mydupr.com/)
- [Research: Batch Recording Workflows](./BATCH_RECORDING.md)
