# Domain Pitfalls

**Domain:** Pickleball Ladder Systems
**Researched:** 2025-05-24

## Critical Pitfalls

Mistakes that cause rewrites or major community issues.

### Pitfall 1: Rating Stagnation (The "Protecting Rank" Problem)
**What goes wrong:** High-ranked players stop playing to avoid risking their rank.
**Why it happens:** Standard ELO systems can penalize a single loss so heavily that top players stay "safe" at the top.
**Consequences:** Leaderboards become static and boring; active players feel cheated.
**Prevention:** Implement a "Rank Decay" for inactivity or require a minimum number of matches per period (e.g., 2 matches/week) to maintain a rank.

### Pitfall 2: Sandbagging
**What goes wrong:** High-skill players enter low-skill divisions to win easily.
**Why it happens:** Financial or social incentives (prizes, ego).
**Consequences:** Ruins the experience for genuine beginners.
**Prevention:** Force-sync with DUPR ratings where possible; allow organizers to "lock" players into specific tiers.

### Pitfall 3: Partner Pairing Bias in Round Robins
**What goes wrong:** A player gets matched with the weakest partner multiple times.
**Why it happens:** Poorly designed rotation algorithms.
**Prevention:** Use standard 4-player or 5-player rotation matrices that ensure everyone plays with everyone else exactly once.

## Moderate Pitfalls

### Pitfall 1: Forfeit Handling
**What goes wrong:** A player drops out mid-ladder, breaking the schedule for others.
**Prevention:** Automated "Sub" pool management; logic to handle 0-0 or "No-Show" results without inflating the opponent's rating unfairly.

### Pitfall 2: Match Reporting Disputes
**What goes wrong:** Player A reports a win, Player B reports a different score.
**Prevention:** Opponent must "Confirm" the score before it impacts ratings.

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Ranking Migration | Resetting ELO to 1200 frustrates veterans. | Import legacy stats/avg scores as a "Starting Seed" for the ELO calculation. |
| DUPR Sync | API Rate limits or stale data. | Cache DUPR ratings for 24 hours; only force-refresh on match report. |
| Shootout Logic | Handling "Ghost" players (odd numbers). | Pre-generate rotation maps for 3, 5, 7, 9... player counts. |

## Sources

- [Pickleball Community Discussions (Reddit/FB)](https://reddit.com/r/pickleball)
- [DUPR Integration Case Studies](https://mydupr.com/)
