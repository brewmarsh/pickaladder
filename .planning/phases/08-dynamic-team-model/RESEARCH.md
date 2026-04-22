# Phase 8: Dynamic Team Model - Research

**Researched:** 2024-05-15
**Domain:** Team Management & Match Recording
**Confidence:** HIGH

## Summary

This research defines the transition from a "Pairing-only" team model to a "Dynamic Team" model that supports flexible rosters (Named Teams). The core challenge is maintaining the integrity of pairing-based stats (ELO/H2H) while allowing users to group themselves into named entities (e.g., "The Smashers") where any combination of members can play together.

**Primary recommendation:** Introduce a `type` field in the `teams` collection to distinguish between `pairing` (auto-generated 2-person) and `named` (user-managed roster) teams. Matches will link to both the specific Pairing (for ELO/pair stats) and the Named Team (for aggregate team stats).

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Firebase Firestore | v1.11.0+ | Document Storage | Primary database, supports `array-contains` and batched writes. [VERIFIED: pyproject.toml] |
| match-stats-service | - | Stat calculation | Internal service for ELO and win/loss logic. [VERIFIED: codebase grep] |

## Architecture Patterns

### Firestore Schema Update (`teams` collection)
The `teams` document structure must be enhanced to support rosters.

```json
{
  "id": "team_abc_123",
  "name": "The Smashers",
  "type": "named",             // "pairing" or "named" [CITED: GROUP_TEAM_REFACTOR.md]
  "member_ids": ["u1", "u2", "u3"], // Flexible roster
  "members": [
    "users/u1", 
    "users/u2", 
    "users/u3"
  ],                           // Document references for joins
  "stats": {
    "wins": 15,
    "losses": 5,
    "elo": 1420
  },
  "createdBy": "u1",           // Owner of named team
  "createdAt": "2024-05-15T...",
  "updatedAt": "2024-05-15T...",
  "isActive": true
}
```

### Distinguishing Pairing vs Named Team
- **Pairing**: Always exactly 2 members. Auto-created by `TeamRepository.get_or_create_team`. Used for ELO tracking of specific duos.
- **Named Team**: 2+ members. Manually created by users. Used for branding and group-level competition.

### Match Document Linkage
To support dual-stat tracking, the match document will be updated:

| Field | Purpose |
|-------|---------|
| `team1Id` / `team1Ref` | **Pairing ID** (Backward compatible). Points to the specific pair that played. |
| `namedTeam1Id` / `namedTeam1Ref` | **Named Team ID** (Optional). Points to the named entity the players represent. |
| `participants` | List of all individual UIDs (Denormalized for easy queries). |

## UI Patterns

### Team Selection & Participant Picking
1. **Selection Mode**: User chooses between "Manual Pair" or "Saved Team".
2. **Saved Team Search**: Autocomplete search for Named Teams the user belongs to.
3. **Roster Expansion**: Once a Named Team is selected, a "Participant Picker" appears showing the roster (member list).
4. **Validation**: Ensure exactly 2 participants are selected for a doubles match (or 1 for singles if team-singles is supported).

## Stat Aggregation Logic

When a match is recorded for a Named Team:

1. **Atomic Update**: Use a Firestore Batch to update:
   - The specific **Pairing** (e.g., [A & B]) stats/ELO.
   - The **Named Team** (e.g., "The Smashers") stats/ELO.
   - The **Individual Players** (A and B) stats.
2. **ELO Calculation**: 
   - Pairing ELO is calculated based on the opponent's Pairing ELO.
   - Named Team ELO can be calculated separately, treating the Named Team as a single entity. [ASSUMED]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Membership Queries | Custom join logic | `array-contains` | Firestore native support for checking if a UID is in `member_ids`. |
| Race Conditions | Client-side increments | `firestore.Increment` | Ensures atomic updates to win/loss counts across concurrent matches. |
| Duplicate Pairings | Complex search logic | `sorted(member_ids)` | Ensures the same pair always resolves to the same Pairing ID. |

## Common Pitfalls

### Pitfall 1: Roster-Pairing Conflict
**What goes wrong:** `TeamRepository.get_team_by_members` might return a Named Team instead of a Pairing if the roster sizes happen to match.
**Prevention:** Always include `type: "pairing"` in the query filter for pair resolution. [VERIFIED: repository.py]

### Pitfall 2: Historical Integrity
**What goes wrong:** Removing a member from a Named Team roster might be interpreted as deleting their match history with that team.
**How to avoid:** Matches must store the UIDs of the people who actually played (`participants` field) rather than just referencing the team roster at the time of query. [CITED: MatchCommandService._resolve_match_participants]

### Pitfall 3: Stat Rollback on Edit
**What goes wrong:** Updating a match score for a Named Team match only updates the Pairing stats, leaving the Named Team stats stale.
**How to avoid:** `MatchStatsUpdater.apply_stats_delta` must be updated to check for and update `namedTeamId` if present.

## Code Examples

### Resolving Pairings and Named Teams
```python
# Refined TeamRepository query
def get_pairing_by_members(cls, db, member_ids: list[str]):
    sorted_ids = sorted(member_ids)
    query = db.collection("teams") \
        .where(filter=firestore.FieldFilter("member_ids", "==", sorted_ids)) \
        .where(filter=firestore.FieldFilter("type", "==", "pairing"))
    # ... return enriched doc
```

### Aggregating Stats in MatchCommandService
```python
def _record_match_batch(batch, match_data, side1_pair_ref, side1_named_ref, ...):
    # Update Pairing
    batch.update(side1_pair_ref, pairing_elo_updates)
    
    # Update Named Team (if provided)
    if side1_named_ref:
        batch.update(side1_named_ref, {
            "stats.wins": firestore.Increment(1),
            "stats.elo": new_named_elo
        })
    
    # Update Individual Users
    for user_ref in side1_user_refs:
        batch.update(user_ref, {"stats.wins": firestore.Increment(1)})
```

## Impact Assessment

### MatchCommandService
- **Method `record_match`**: Needs to accept `team_1_id` and `team_2_id` from the UI submission.
- **Method `_resolve_teams`**: Needs to return both Pairing and Named Team references.
- **Method `_record_match_batch`**: Needs to handle updates for up to 4 team-like entities (2 Pairings + 2 optional Named Teams).

### TeamRepository.get_or_create_team
- Must be updated to explicitly filter for `type: "pairing"`.
- This ensures that auto-pairing logic never accidentally "hijacks" a Named Team document.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Named Teams should have their own ELO. | Stat Aggregation | If teams only want win/loss counts, ELO logic adds unnecessary complexity to the update batch. |
| A2 | Users can only belong to a "Named Team" if it's explicitly created. | Summary | If we want to auto-create Named Teams, the UI flow changes significantly. |

## Open Questions (RESOLVED)

1. **Can a Named Team play Singles?**
   - **Resolved:** Yes, the logic will be generic enough to support 1-person rosters or participants. A "team" is a generic container for 1 or more players.
2. **Team Roles?**
   - **Resolved:** A simple `createdBy` field for the owner is sufficient for Phase 8. Full RBAC (Role Based Access Control) is deferred to a later milestone.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Firestore | Data layer | ✓ | 1.11.0 | — |
| Python | Backend | ✓ | 3.12 | — |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Quick run command | `pytest tests/test_team_service.py` |
| Full suite command | `pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TEAM-01 | Create Named Team with Roster | Unit | `pytest tests/test_team_service.py::test_create_named_team` | ❌ Wave 0 |
| TEAM-02 | Resolve Pairing within Named Team | Integration | `pytest tests/test_match_recording.py::test_named_team_resolution` | ❌ Wave 0 |
| TEAM-03 | Aggregate Stats for Named Team | Integration | `pytest tests/test_match_stats.py::test_named_team_stat_aggregation` | ❌ Wave 0 |

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V4 Access Control | Yes | Verify `createdBy` before allowing roster edits. |
| V5 Input Validation | Yes | Validate `member_ids` are valid UIDs in `teams.create`. |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Unauthorized Roster Change | Tampering | Server-side check that `current_user == team.createdBy`. |
| Stat Manipulation | Tampering | Use Firestore Security Rules to restrict direct updates to `stats` fields. |

## Sources

### Primary (HIGH confidence)
- `pickaladder/teams/repository.py` - Current team resolution logic.
- `pickaladder/match/services/command.py` - Match recording workflow.
- `.planning/research/GROUP_TEAM_REFACTOR.md` - Original architecture proposal.

### Metadata
**Confidence breakdown:**
- Standard stack: HIGH - Core project technology.
- Architecture: HIGH - Consistent with Firestore best practices and existing patterns.
- Pitfalls: MEDIUM - Based on common Firestore anti-patterns.

**Research date:** 2024-05-15
**Valid until:** 2024-06-15
