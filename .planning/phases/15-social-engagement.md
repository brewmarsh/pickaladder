# Phase 15: Social Engagement & Feed

**Goal:** Transform pickaladder into a more interactive community by surfacing activity and enabling social engagement.

## Objectives
1. **Global Activity Feed:** A unified stream of events (Match results, Tournament wins, Promotion events).
2. **Reactions & Engagement:** Allow users to "Cheer" or "Congratulate" activities on the feed.
3. **Community Highlights:** Surface trending players or groups based on recent activity.

## Implementation Plan

### 1. Feed Infrastructure
- Implement `ActivityService` to log events from existing workflows (e.g., when a match is recorded).
- Create a `FeedRepository` to query aggregated events.

### 2. Social Interactions
- Implement a lightweight "Reactions" system (Emoji-based).
- Add support for threaded comments or simple text-based congrats.

### 3. UI/UX
- Build the "Community Feed" component for the dashboard.
- Create interactive notification badges for social interactions.

## Success Criteria
1. Users see a live feed of recent matches and season completions on their dashboard.
2. Users can react to feed items with at least one interaction type (e.g., "Cheer").
3. Feed is paginated and performant, using event-driven logging.
