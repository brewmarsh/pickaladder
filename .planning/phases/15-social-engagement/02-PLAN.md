# Plan: 15-02: Social Reactions & Interactive Engagement

**Goal:** Enable community interaction by allowing users to react to feed activities.

## Tasks
1. [ ] Update `ActivityService.add_reaction(activity_id, user_id, type)`:
    - Appends a reaction object `{userId, type, timestamp}` to the `reactions` array.
    - Prevents duplicate reactions from the same user on the same item.
2. [ ] Implement `api/feed/<activity_id>/react` POST route.
3. [ ] Update `user_dashboard.html` Feed Component:
    - Add a "Cheer" button (⚡ or 🎾) to each activity item.
    - Display reaction count and a list of users who reacted (on hover).
    - Use AJAX to toggle reactions without page refresh.
4. [ ] Create unit tests for the reaction engine.

## Technical Details
- **Schema:** `reactions` is an array of maps on the Activity document.
- **Frontend:** Use the `fetch()` API and optimistic UI updates for a snappy social feel.

## Success Criteria
- [ ] Users can click a button on a feed item and see the reaction count increment.
- [ ] Users can remove their own reaction by clicking the same button.
