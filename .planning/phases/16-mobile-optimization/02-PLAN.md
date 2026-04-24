# Plan: 16-02: Offline Sync & Service Worker Logic

**Goal:** Implement robust offline match recording and sync capabilities to handle poor courtside connectivity.

## Tasks
1. [x] Implement `pickaladder/static/js/offline_store.js` using IndexedDB (Dexie.js or vanilla) to store pending matches.
2. [x] Update `pickaladder/static/js/match_recording.js` to check connectivity before submission and store locally if offline.
3. [x] Enhance `service-worker.js` with Background Sync API support (or a manual periodic sync fallback).
4. [x] Create `pickaladder/templates/components/_offline_indicator.html` to notify users when they are working offline.
5. [x] Update `user/dashboard` to show "Pending Sync" counts for the user.

## Technical Details
- **Storage:** Use IndexedDB to persist match data (scores, participant IDs, timestamps).
- **Sync:** When `navigator.onLine` becomes true, trigger a bulk upload of pending matches.
- **Validation:** Offline matches must be re-validated against the server schema before final ingestion.

## Success Criteria
- [x] A match can be recorded and "saved" while the device is in Airplane Mode.
- [x] The saved match is automatically uploaded to Firestore once connectivity is restored.
- [x] Users see a visual confirmation of their sync status.
