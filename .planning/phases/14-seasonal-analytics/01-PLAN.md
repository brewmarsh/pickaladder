# Plan: 14-01: Analytics Core & User History

**Goal:** Implement the data extraction engine to show users their performance across all completed seasons.

## Tasks
1. [ ] Implement `AnalyticsService.get_user_season_history(user_id)`:
    - Scans all completed seasons in the database.
    - Extracts the user's rank, wins, losses, and PD from `finalStandings`.
2. [ ] Add `user/analytics` API route to expose this data.
3. [ ] Update `pickaladder/templates/user/profile.html` to include a "Season History" table.
4. [ ] Create unit tests for historical data extraction.

## Technical Details
- **Data Source:** Primary source is the `finalStandings` field on Season documents.
- **Optimization:** Filter seasons by `status=COMPLETED` to avoid heavy match calculation during analytics retrieval.

## Success Criteria
- [ ] Users can see a list of their past seasons with their final rank and stats.
- [ ] Logic correctly identifies the user even if they've changed their username (uses UID).
