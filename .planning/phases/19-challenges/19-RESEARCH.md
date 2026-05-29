# Phase 19: Competitive Challenges & Wagering - Research

**Researched:** 2026-04-24
**Domain:** Competitive Social Features & Virtual Economy
**Confidence:** HIGH

## Summary
Phase 19 introduces a formal "Challenge" system and a "Social Credits" economy. Currently, "Challenge" buttons exist in the UI (Leaderboard, Profile, Community) but they simply shortcut to the "Record Match" flow. This phase will replace that with a persistent challenge lifecycle and a virtual currency.

## Standard Stack
- **Database:** Firestore (New `challenges` collection).
- **Backend:** Flask/Python (Updates to `User` model and `Match` processing).
- **Notifications:** Firebase Cloud Messaging (FCM) and existing Firestore-based real-time listeners.

## Key Findings

### 1. User Data Model & Credits
- **Current State:** The `User` model has no fields for `social_credits`.
- **Recommendation:** Add `social_credits` (int) to the `User` Firestore document. Initialize at 100 for existing users.
- **Transactions:** Use Firestore transactions for credit transfers to ensure atomicity.

### 2. Challenge Logic & Lifecycle
- **States:** `pending`, `accepted`, `completed`, `expired`, `declined`.
- **Linking:** The `Challenge` document should store:
  - `challenger_id`, `challenged_id`
  - `status`
  - `wager_amount`
  - `match_id` (null until completed)
  - `expires_at` (Timestamp)
- **Automatic Resolution:** When a match is recorded between participants of an `accepted` challenge, link the match and resolve the wager.

### 3. Notifications
- **Triggers:** New challenge received, challenge accepted/declined.
- **Implementation:** Reuse patterns in `pickaladder/static/js/notifications.js`.

### 4. UI Integration
- **Leaderboard/Profile:** Update "Challenge" icons to trigger a "Create Challenge" modal (set wager/deadline).
- **Dashboard:** Add a "Challenge Hub" widget for managing active challenges.

## Common Pitfalls
- **Credit Inflation:** Credit generation must be tightly controlled (e.g., daily reward or match completion).
- **Stale Challenges:** Must handle expiration of challenges that are never played.

## Validation Architecture
- **Framework**: Pytest.
- **Strategy**: Unit tests for challenge state transitions; integration tests for wagering transactions.
