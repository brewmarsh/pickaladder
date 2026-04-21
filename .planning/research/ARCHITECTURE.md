# Architecture Patterns

**Domain:** Pickleball Ladder Systems
**Researched:** 2024-10-24 (Updated with Batch Recording)

## Recommended Architecture

The system should follow a **Service-Oriented Pattern** within the Flask application, isolating rating logic from data persistence.

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| **Session Service** | **Manages player pools and "in-progress" session state.** | **Match Service, Firestore** |
| Match Service | Records individual match results, triggers validation. | Firestore, Rating Service |
| Rating Service | Calculates ELO, Upset probability, DUPR sync. | Match Service, User Service |
| Leaderboard Service | Aggregates user stats for group display. | Firestore, Match Service |
| Event Engine | Generates court assignments for Shootouts/Round-Robins. | User Service, Group Service |

### Data Flow

1. **Session Setup:** User creates a Session and selects a "Player Pool" (Firestore: `sessions` collection).
2. **Match Entry:** User submits scores via Batch UI (Firestore: `matches` collection, linked to `sessionId`).
3. **Calculation:** Rating Service updates ELO/stats for all participants.
4. **Broadcast:** Leaderboards are updated.

## Patterns to Follow

### Pattern 1: Strategy Pattern for Ratings
Allows switching between ELO, DUPR, or internal systems.

### Pattern 2: **Session-Scoped Player Pool**
Instead of querying the entire group roster for every match, the UI should use a pre-filtered "Session Pool" stored in local state or a temporary `session` document.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Heavy In-Memory Aggregation
Fetching ALL matches for a group to calculate a leaderboard on every request.

### Anti-Pattern 2: **Stateless Batch Entry**
**Problem:** Forcing the user to re-select players if the app crashes or they switch tabs during a session.
**Instead:** Persist the "Active Session" pool in Firestore or LocalStorage so it remains available throughout the day.

## Scalability Considerations

| Concern | At 100 users | At 10K users | At 1M users |
|---------|--------------|--------------|-------------|
| DB Reads | Real-time streams | Filtered queries | Distributed caching (Redis) |
| Ranking Calcs | Synchronous | Async Task (Celery) | Batch processing |
| Leaderboards | On-the-fly | Incremental updates | Pre-computed materialized views |

## Sources

- [Firestore Best Practices](https://firebase.google.com/docs/firestore/best-practices)
- [Clean Architecture in Python](https://pypi.org/project/clean-architecture/)
- [Research: Batch Recording Workflows](./BATCH_RECORDING.md)
