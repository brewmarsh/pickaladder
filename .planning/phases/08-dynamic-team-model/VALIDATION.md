# Validation Plan: Phase 8 - Dynamic Team Model

## Objectives
- Support named teams with rosters (>2 members).
- Enable participant selection from named team rosters during match recording.
- Aggregate performance metrics for both pairings and named teams.

## Verification Tasks

### 1. Schema Transition (DYNAMIC-01)
- **Check**: Verify 'teams' collection supports `type` (pairing/named) and `memberIds` array.
- **Success Criteria**: New `named` teams can be created with more than 2 members.

### 2. Match Recording (DYNAMIC-02)
- **Check**: Record a doubles match where one "side" is a Named Team, and two specific members from that team's roster are selected as participants.
- **Success Criteria**: Match document correctly references both the Named Team ID and the specific Pairing ID.

### 3. Stat Aggregation (DYNAMIC-03)
- **Check**: Verify that a win for a pairing also increments the `wins` count for the associated Named Team.
- **Success Criteria**: Statistics are correctly propagated up from pairing to named team level.

## Regression Testing
- Run full test suite: `uv run pytest`
- Specifically monitor:
    - `tests/test_team_service.py`
    - `tests/test_match_transaction.py`
    - `tests/test_ranking_integrity.py`

## User Experience Check
- Verify that the "Record Match" form correctly filters participants when a Named Team is selected.
