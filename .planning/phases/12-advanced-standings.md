# Phase 12: Advanced Standings & Tie-breaks

**Goal:** Implement robust, tournament-standard standing aggregation with complex tie-break rules.

## Objectives
1. Implement the **USAP Hierarchical Tie-break** logic.
2. Develop a recursive **Tie-break Reset** engine.
3. Update **Season and Tournament dashboards** with detailed stat columns (PD, Points For).
4. Provide transparency into *why* a player is ranked higher in a tie.

## Implementation Plan

### 1. Data Service Enhancement
- Refactor `SeasonStandingsService` to extract logic into a standalone `StandingAggregator`.
- Ensure aggregator has access to the full match history of the season/tournament.

### 2. Hierarchical Sorting
- Implement `calculate_rankings(participants, matches)` with support for:
    - Head-to-Head (H2H) results.
    - Global and H2H Point Differential.
    - Points For (PF).

### 3. UI Update
- Add tooltips or small text indicators explaining tie-break wins (e.g., "Winner via H2H").
- Expand table headers to include `PF` (Points For) and `PA` (Points Against).

## Success Criteria
1. Rankings correctly reflect H2H results when match wins are equal.
2. Three-way ties are resolved via Point Differential or Reset Rule.
3. Standings dashboard displays all data points used in the hierarchy.
