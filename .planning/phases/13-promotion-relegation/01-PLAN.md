# Plan: 13-01: Movement Rules & Engine

**Goal:** Implement the logic to calculate which players/teams should be promoted or relegated based on standings.

## Tasks
1. [ ] Update `Season` model to store `movementRules` (JSON object).
    - `promotionCount`: int
    - `relegationCount`: int
2. [ ] Implement `SeasonFinalizationService`:
    - `calculate_movements(season_id)`: Using `SeasonStandingsService`, determine up/down targets.
    - `snapshot_standings(season_id)`: Store a final JSON copy of the standings for history.
3. [ ] Add `finalize_season(season_id)` route to the season blueprint.
4. [ ] Create unit tests for movement calculation across multiple divisions.

## Technical Details
- **Movement Rules:** 
    - Top Division: 0 promoted, X relegated.
    - Middle Divisions: X promoted, Y relegated.
    - Bottom Division: X promoted, 0 relegated.
- **Standings Snapshot:** To be stored in a sub-collection `/seasons/{sid}/finalStandings`.

## Testing Strategy
- **Scenario A:** 3 divisions. Top 2 from Div 2 move to Div 1. Bottom 2 from Div 1 move to Div 2.
- **Scenario B:** Handling ties at the movement boundary (should use the Phase 12 tie-breakers).
