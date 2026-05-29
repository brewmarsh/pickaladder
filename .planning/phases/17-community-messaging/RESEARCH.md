# Phase 17: Community Messaging - Research

**Researched:** 2026-04-24
**Domain:** Real-time Messaging / Firestore
**Confidence:** HIGH

## Summary
The messaging infrastructure is partially scaffolded with a `MessagingRepository` and `MessagingService`. The core goal is to transition the current "Post-and-Reload" chat into a real-time experience using Firestore's client-side SDK while ensuring strict security rules.

## Standard Stack
- **Backend**: `firebase-admin` for creating conversations and server-side validation.
- **Frontend**: Firebase JS SDK v8 (already initialized in `layout.html`).
- **Database**: Firestore (Collections: `conversations`, Sub-collections: `messages`).

## Architecture Patterns
- **Repository Pattern**: Continue using `MessagingRepository` for server-side fetches.
- **Real-time Listener**: Implement `db.collection('conversations').doc(cid).collection('messages').onSnapshot(...)` in a new `chat.js`.
- **Hybrid Auth**: Use the `firebaseIdToken` stored in `localStorage` (managed in `layout.html`) to authenticate client-side Firestore requests.

## Common Pitfalls
- **Security Rules**: Ensure `conversations` can only be read if `request.auth.uid in resource.data.participants`.
- **Timestamp Handling**: Firestore `SERVER_TIMESTAMP` behaves differently on client vs server; ensure UI handles the "pending" local state (optimistic UI).

## UI Integration Points
- **Profile Page**: Add a "Message" button to `pickaladder/templates/user/view_user.html` (or equivalent) linking to `messaging.start_chat`.
- **Inbox**: Already linked in `navbar.html`.

## Validation Architecture
- **Framework**: Pytest (existing).
- **Test Strategy**: Mock Firestore for repository tests; use Playwright (detected in docs) for E2E chat flow verification.
