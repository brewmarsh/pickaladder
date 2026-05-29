# Phase 17 Plan 03: Real-time Notifications & Push Summary

Implemented real-time global notifications and unread badges across the application, integrating with the existing PWA infrastructure for push support.

## Key Changes

### Backend
- **MessagingService**: Added `get_total_unread_count` to sum unread messages for a user across all conversations.
- **Context Processors**: Added `inject_unread_messages_count` to provide the unread count to all templates.
- **User Routes**: Added `/api/save_fcm_token` POST route to persist FCM registration tokens in Firestore.

### Frontend
- **Navbar**: Added `#unread-messages-badge` to both desktop and mobile "Messages" links to show real-time unread counts.
- **Notifications JS**: Created `notifications.js` which:
  - Listens to real-time Firestore updates on the `conversations` collection.
  - Updates navbar badges automatically when messages are received or marked as read.
  - Triggers in-app toast notifications for new messages received while on other pages.
  - Requests FCM push permission and registers the token with the server.
- **Layout**: Integrated `firebase-messaging.js`, `notifications.js`, and exposed `currentUserId` to the client.

### Service Worker
- **Service Worker**: Updated `service-worker.js` to:
  - Import Firebase app and messaging scripts.
  - Handle background push notifications via `setBackgroundMessageHandler`.
  - Cache `notifications.js` for offline support.

## Verification Results

### Automated Tests
- Verified `get_total_unread_count` exists in `pickaladder/messaging/services.py`.
- Verified `unread-messages-badge` exists in `pickaladder/templates/navbar.html`.
- Verified `importScripts` for Firebase exists in `pickaladder/static/service-worker.js`.

### Manual Verification Steps (Planned)
1. Log in as a user and navigate to the Dashboard.
2. Send a message to this user from another account/device.
3. Observe the "Messages" badge in the navbar update from 0 to 1.
4. Observe a toast notification appearing with the message content.
5. Grant notification permissions and verify the FCM token is saved in the user's Firestore document.

## Deviations from Plan
- None - plan executed as written.

## Threat Flags
| Flag | File | Description |
|------|------|-------------|
| threat_flag: Information Disclosure | pickaladder/static/js/notifications.js | Toast notifications show message content in plain text on screen. |
| threat_flag: Denial of Service | pickaladder/user/routes.py | `/api/save_fcm_token` endpoint updates Firestore; should be monitored for spamming. |

## Self-Check: PASSED
