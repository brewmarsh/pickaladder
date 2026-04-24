# Plan: 12-01: Standing Aggregator Core

**Goal:** Implement the complex hierarchical sorting logic in the backend.

## Tasks
1. [ ] Create `pickaladder/core/ranking/aggregator.py`.
2. [ ] Implement `StandingAggregator` with:
    - `aggregate_basic_stats(matches)`: Wins, Losses, PF, PA.
    - `resolve_ties(tied_players, matches)`: Recursive H2H/PD/PF resolution.
3. [ ] Update `SeasonStandingsService` to use the new aggregator.
4. [ ] Create a dedicated unit test suite `tests/test_standing_aggregator.py` with specific tie scenarios (2-way H2H, 3-way cycle).

## Technical Details
- **Tied Groups:** The aggregator should group players by "Matches Won".
- **H2H Matrix:** For any tied group, build a sub-matrix of match results only between those members.
- **Recursive Pass:** If a group is partially broken (e.g., 3-way tie becomes 1st and a 2-way tie), recurse on the remaining 2-way tie from the top of the hierarchy.

## Testing Strategy
- **Scenario A:** P1 beat P2, both have 5 wins. P1 > P2.
- **Scenario B:** P1 > P2, P2 > P3, P3 > P1 (Cycle). Resolve via PD.
- **Scenario C:** P1 and P2 have identical everything. Stable sort.
