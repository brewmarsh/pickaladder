# Research: Pickleball Tie-Break Rules (USAP Standard)

**Date:** 2026-04-24
**Context:** Defining advanced standing aggregation for Milestone 7.

## Tie-Break Hierarchy
According to USAP (USA Pickleball) standards, ties in Round Robin or Season standings are broken using the following order:

1.  **Matches Won:** Total number of matches won in the round-robin/season.
2.  **Head-to-Head (H2H):** Match result(s) between the tied teams/players.
3.  **Point Differential (All Games):** (Total Points For) - (Total Points Against) across all played matches.
4.  **H2H Point Differential:** Point differential restricted to matches between the tied teams.
5.  **Point Differential vs. Next-Highest:** Comparison of point differentials against the next-highest ranked team (e.g., if tied for 2nd, check vs 1st).
6.  **Total Points Scored:** Most total points accumulated across all matches.

## Procedural Nuances
- **Reset Rule:** Once a tie is broken (e.g., in a 3-way tie where one team is clearly 1st), the remaining tied teams **restart** from step 2 (H2H) to determine the next rank.
- **Forfeits:** Typically, forfeited matches do not count toward standings math (except for rating impact).

## Technical Implementation Strategy
- **Service Layer:** `StandingAggregationService` should handle the multi-pass sorting logic.
- **Data Requirement:** Standing calculation requires the full match record, not just win/loss counts, to calculate H2H and PD.
- **Sorting Logic:** Implement a Python sorting key or a multi-pass filtering function to apply the hierarchy and the Reset Rule.
