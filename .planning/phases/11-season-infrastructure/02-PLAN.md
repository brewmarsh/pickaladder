# Plan: 11-02: Division Support & Standings Aggregation

**Goal:** Allow group admins to organize seasons into divisions and automatically calculate standings.

## Tasks
1. [ ] Update `Season` model to support explicit `divisions` (name + participant pool).
2. [ ] Implement `SeasonStandingsService`:
    - `calculate_standings(season_id)`: Aggregate match results for participants within the season's start/end dates.
    - Support sorting by wins, win percentage, and point differential.
3. [ ] Build the "Season Dashboard" UI:
    - Display current standings table.
    - Show recent season matches.
4. [ ] Integrate "Season Standings" into the main Season list view.
5. [ ] Add unit tests for standing aggregation logic.

## Technical Details
- **Standings Calculation:** Query all completed matches where `tournamentId` is None (if we want general group play seasons) or matches linked to tournaments within that season. Actually, let's allow linking tournaments to a Season.
- **Data Association:** Update `Tournament` model to include an optional `seasonId`.

## Success Criteria
- [ ] Standings are calculated correctly based on match results.
- [ ] Users can see their rank within a specific season.
- [ ] Divisions correctly segment the participant pool.
