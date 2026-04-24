# Plan: 13-02: Next Season Creation & Transition Apply

**Goal:** Automate the creation of a new season with participants moved to their new divisions.

## Tasks
1. [ ] Implement `SeasonService.clone_for_next_season(old_season_id, new_name)`:
    - Creates a new Season document.
    - Copies movement rules.
2. [ ] Implement `TransitionService.apply_movements(old_season_id, new_season_id)`:
    - Takes the calculated movements from Phase 13-01.
    - Updates the new season's divisions with the promoted/relegated players.
3. [ ] Add "Start Next Season" button to the finalized Season view.
4. [ ] Create a UI wizard for the transition process.

## Technical Details
- **Participant Mapping:**
    - Promoted players from Div N go to Div N-1.
    - Relegated players from Div N go to Div N+1.
    - Retained players stay in Div N.

## Success Criteria
- [ ] A new season is created with one click from a completed season.
- [ ] The new season's divisions are correctly populated based on previous performance.
- [ ] All 100% passing tests for the transition engine.
