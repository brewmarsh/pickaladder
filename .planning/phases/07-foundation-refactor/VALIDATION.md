# Validation Plan: Phase 7 - Group & Team Foundation Refactor

## Objectives
- Standardize entity schemas (specifically timestamps).
- Implement a consistent Repository pattern across groups and teams.
- Improve data access efficiency through batch operations.

## Verification Tasks

### 1. Schema Consistency (REFACTOR-01)
- **Check**: Run `scripts/migrate_timestamps_v7.py` and verify at least 2 collections ('teams', 'group_invites') are updated.
- **Check**: Audit `tests/test_referral.py` to ensure it uses `createdAt`.
- **Success Criteria**: No occurrences of `created_at` or `updated_at` remain in the core entity models or logic.

### 2. Repository Pattern (REFACTOR-03)
- **Check**: Verify `BaseRepository` unit tests (add if needed).
- **Check**: Ensure `GroupRepository` and `TeamRepository` successfully fetch data using `BaseRepository` methods.
- **Success Criteria**: `GroupService` and `TeamService` no longer call `db.collection(...).document(...)` directly.

### 3. Logic Consolidation (REFACTOR-02)
- **Check**: Verify team creation via both `TeamService` and `MatchCommandService` triggers the same validation and ID generation logic.
- **Success Criteria**: Single point of truth for team instantiation.

## Regression Testing
- Run full test suite: `uv run pytest`
- Specifically monitor:
    - `tests/test_group.py`
    - `tests/test_team_service.py`
    - `tests/test_match_transaction.py`

## Performance Benchmarks
- Compare match recording time (which creates teams) before and after refactor.
