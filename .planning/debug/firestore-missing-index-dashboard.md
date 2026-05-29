---
status: verifying
trigger: "firestore-missing-index-dashboard"
created: 2025-05-22T08:00:00Z
updated: 2026-05-22T10:30:00Z
---

## Current Focus
hypothesis: Missing Firestore composite index on the 'teams' collection for fields (type, stats.elo).
test: N/A - The root cause is identified from the code analysis.
expecting: Adding the index to `firestore.indexes.json` or creating it in the Firebase console will resolve the 500 error.
next_action: Human verification required to confirm index deployment and dashboard fix.

## Symptoms
expected: Dashboard loads without errors.
actual: 500 Internal Server Error when accessing /user/dashboard.
errors: `google.api_core.exceptions.FailedPrecondition: 400 The query requires an index.`
reproduction: Access /user/dashboard.
started: Not specified.

## Eliminated
<!-- APPEND only - prevents re-investigating -->

## Evidence
<!-- APPEND only - facts discovered -->

- timestamp: 2026-05-22T10:00:00Z
  checked: `pickaladder/user/services/dashboard.py` and `pickaladder/teams/services.py`
  found: The `dashboard` route calls `get_dashboard_data` -> `_fetch_social_and_tournaments` -> `TeamService.get_top_teams(db, limit=3)`.
  implication: `TeamService.get_top_teams` performs a query on the 'teams' collection: `db.collection('teams').where('type', '==', 'named').order_by('stats.elo', 'DESCENDING').limit(limit)`. This requires a composite index on (type, stats.elo).

## Resolution
root_cause: Missing Firestore composite index for query on 'teams' collection: (type, stats.elo).
fix: Added missing composite index for 'teams' collection to `firestore.indexes.json`.
verification: Pending deployment of Firestore indexes.
files_changed: ["firestore.indexes.json"]
