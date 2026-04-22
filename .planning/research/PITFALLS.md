# Domain Pitfalls

**Domain:** Sports/Pickleball Ladder App
**Researched:** 2026-04-21

## Critical Pitfalls

### Pitfall 1: Inconsistent Data Schema
**What goes wrong:** `createdAt` vs `created_at`.
**Why it happens:** Lack of standardized repository/model layer.
**Consequences:** Sorting by date breaks if different documents use different keys.
**Prevention:** Strict Pydantic models and a single Repository for each collection.

### Pitfall 2: Static Pairing Rigidity
**What goes wrong:** Assuming a "Team" always consists of the same two people.
**Why it happens:** Simple initial data modeling for doubles.
**Consequences:** Users cannot create a "Team" for their club or group of friends. Performance history for "The Fireballs" is fragmented across every pair combination.
**Prevention:** Implement a "Named Team" entity with a roster (junction table).

## Moderate Pitfalls

### Pitfall 1: Real-time vs Cached Stat Divergence
**What goes wrong:** Group leaderboard shows 5 wins, Team dashboard shows 10 wins.
**Why it happens:** Group leaderboard scans only recent matches (limited to 20); Team dashboard uses stored stats.
**Prevention:** Use the same Service method for all stat calculations or implement robust denormalization.

## Minor Pitfalls

### Pitfall 1: Auto-Friending Friction
**What goes wrong:** Users find themselves "friends" with people they don't know just because they joined a large public group.
**Prevention:** Make auto-friending an opt-in group setting.

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Standardization | Breaking existing queries. | Run a migration script to rename `created_at` to `createdAt` before deploying code changes. |
| Dynamic Teams | N+1 Query problem. | Use Firestore `db.get_all(refs)` for batch fetching member profiles. |
| Repository Extraction | Circular dependencies. | Ensure Repositories do not import Services. |

## Sources
- Codebase audit of `group_service.py` and `teams/services.py`.
- Community feedback on similar sports apps (Playtomic, DUPR).
