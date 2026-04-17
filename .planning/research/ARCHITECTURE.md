# Architecture Patterns

**Domain:** Pickleball Ladder Systems
**Researched:** 2025-05-24

## Recommended Architecture

The system should follow a **Service-Oriented Pattern** within the Flask application, isolating rating logic from data persistence.

### Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| Match Service | Records match results, triggers validation. | Firestore, Rating Service |
| Rating Service | Calculates ELO, Upset probability, DUPR sync. | Match Service, User Service |
| Leaderboard Service | Aggregates user stats for group display. | Firestore, Match Service |
| Event Engine | Generates court assignments for Shootouts/Round-Robins. | User Service, Group Service |

### Data Flow

1. **Match Entry:** User submits scores via UI.
2. **Validation:** System checks for conflicting scores or "impossible" results.
3. **Calculation:** Rating Service updates ELO/stats for all participants.
4. **Broadcast:** Leaderboards are updated (cached or real-time Firestore stream).

## Patterns to Follow

### Pattern 1: Strategy Pattern for Ratings
Allows switching between ELO, DUPR, or internal point systems without rewriting the Match Service.

```python
class RatingStrategy(Protocol):
    def calculate(self, winner_data, loser_data) -> tuple[dict, dict]: ...

class EloStrategy:
    def calculate(self, winner_data, loser_data):
        # Existing Elo logic
        ...

class DuprStrategy:
    def calculate(self, winner_data, loser_data):
        # DUPR API sync logic
        ...
```

### Pattern 2: Optimistic Leaderboard Updates
Since Firestore is real-time, the leaderboard should listen to the `matches` collection filtered by `groupId` to update instantly when a new match is recorded.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Heavy In-Memory Aggregation
**What:** Fetching ALL matches for a group to calculate a leaderboard on every request.
**Why bad:** Performance degrades linearly with the number of matches.
**Instead:** Maintain a "Leaderboard" or "Stats" document per user-group relationship that is updated incrementally when matches are recorded.

## Scalability Considerations

| Concern | At 100 users | At 10K users | At 1M users |
|---------|--------------|--------------|-------------|
| DB Reads | Real-time streams | Filtered queries | Distributed caching (Redis) |
| Ranking Calcs | Synchronous | Async Task (Celery) | Batch processing |
| Leaderboards | On-the-fly | Incremental updates | Pre-computed materialized views |

## Sources

- [Firestore Best Practices](https://firebase.google.com/docs/firestore/best-practices)
- [Clean Architecture in Python](https://pypi.org/project/clean-architecture/)
