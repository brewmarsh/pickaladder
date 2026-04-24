# Plan: 15-01: Event Logging & Base Feed

**Goal:** Implement the backend system to capture community events and expose them as a feed.

## Tasks
1. [ ] Define `Activity` model in a new `pickaladder/core/activity` module.
    - Fields: `userId`, `type` (MATCH_COMPLETED, SEASON_FINALIZED, RANK_CHANGE), `data` (JSON), `timestamp`.
2. [ ] Implement `ActivityService.log_activity(type, user_id, data)`:
    - Writes events to a global `/activities` collection.
3. [ ] Integrate logging into:
    - `MatchService` (on completion).
    - `SeasonFinalizationService` (on season close).
4. [ ] Implement `FeedService.get_global_feed(limit)`:
    - Returns a list of recent activities enriched with user profile data.
5. [ ] Create unit tests for activity logging.

## Technical Details
- **Storage:** Firestore global collection `/activities` with index on `timestamp DESC`.
- **Enrichment:** Use the `UserService` to attach usernames and avatars to the feed items.

## Success Criteria
- [ ] Every time a match is recorded, a corresponding entry appears in the `/activities` collection.
- [ ] API can return the last 20 events in chronological order.
