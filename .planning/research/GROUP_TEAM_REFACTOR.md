# Research: Group and Team Refactor

**Project:** pickaladder
**Researched:** 2026-04-21
**Confidence:** HIGH

## 1. Architectural Audit

### Inconsistencies Found
| Component | Issue | Impact |
|-----------|-------|--------|
| **Timestamps** | `createdAt` vs `created_at` | Inconsistent schema across Firestore documents. `createdAt` is used in ~80% of the codebase, but `teams/models.py` uses `created_at`. |
| **Team Creation** | Duplicate Logic | `teams/services.py` and `teams/models.py` both implement team creation with slight variations in field names. |
| **Service Patterns** | Procedural vs Repository | `GroupService` uses static methods with passed `db` clients. `MatchCommandService` inherits from `BaseRepository` but functions as a service. No clear boundary between data access and business logic. |
| **Stat Calculation** | Divergent Sources | Group leaderboard calculates team stats from the last 20 matches. Team dashboard uses stats stored on the Team document. These can diverge if a team plays >20 matches or across multiple groups. |

### Component Boundaries
- **Groups**: Act as "Clubs" or "Ladders". They own the membership list and recent match context.
- **Teams**: Currently act as "Pairings". A team is uniquely identified by its members (usually 2).
- **Matches**: Reference a Group and two Teams (or Players for singles).

## 2. Dynamic Teams vs Static Teams

### Current Model: Static Pairings
- A "Team" is an immutable set of players (e.g., [UserA, UserB]).
- If UserA plays with UserC, it is a completely separate Team entity.
- Pros: Simple pairing stats, easy ELO tracking for pairs.
- Cons: Cannot have a "Team" with a roster (e.g., "The Smashers" with 5 members where any 2 can play).

### Proposed Model: Dynamic/Hybrid
- **Pairs (Ephemeral/Auto)**: Continue auto-generating entities for unique pairings to maintain ELO and H2H history.
- **Teams (Managed/Named)**: Introduce a "Team" entity that has a `roster`. Users can create a named team, invite members, and select this team when recording a match.
- **Roster Management**: Use a `memberships` collection to link Users to Teams with roles (Owner, Member).

## 3. UX Friction Points

1.  **Naming Friction**: Teams are auto-named "Player A & Player B". Renaming requires navigating to the team page, which is not obvious during match recording.
2.  **Match Recording**: The UI asks for "Partner" and "Opponents" but doesn't allow selecting a pre-existing "Named Team".
3.  **Group Management**: Admin actions (Promote/Demote/Remove) are spread across static methods in `GroupService`. The UI for managing a large group is likely cumbersome.
4.  **Auto-Friending**: `GroupService` automatically friends group members. This might be a privacy concern or unexpected for some users.

## 4. Proposed Standardized Pattern

### Repository/Service Separation
1.  **Repository**:
    - `BaseRepository` should handle Firestore interaction (get, set, update, delete, batch).
    - Specific repositories (e.g., `GroupRepository`, `TeamRepository`) handle collection-specific queries.
    - No business logic or "enrichment" in the repository.
2.  **Service**:
    - Orchestrates repositories.
    - Handles "Enrichment" (e.g., `GroupService.get_group_details` fetching members, stats, matches).
    - Business logic (ELO, Stat aggregation).

### Standardized Entity Schema
- Use `createdAt` and `updatedAt` (camelCase) for all Firestore documents.
- Use `id` (string) for document IDs in dictionaries returned by services.
- Use `DocumentReference` for relationships in Firestore, but strings in API/Form data.

## 5. Implementation Roadmap Recommendations
1.  **Phase 1: Standardization**: Align timestamp fields and merge duplicate creation logic.
2.  **Phase 2: Repository Extraction**: Extract data access from `GroupService` and `TeamService` into repositories.
3.  **Phase 3: Named Teams**: Implement the `roster` model for Teams, allowing a Team to have >2 members.
4.  **Phase 4: UX Overhaul**: Update match recording to support selecting Named Teams.
