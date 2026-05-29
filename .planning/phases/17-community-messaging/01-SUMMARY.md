# Phase 17 Plan 01: Messaging Backend & Security Summary

Updated the messaging backend infrastructure to support real-time metadata (unread counts, last message tracking) and defined secure access patterns via Firestore Security Rules.

## Key Changes

### Messaging Metadata & Logic
- **MessagingRepository.add_message**: Now automatically increments the `unreadCount` for the recipient and stores `lastMessageSenderId` in the conversation document.
- **MessagingRepository.mark_as_read**: Added capability to reset the unread count for a specific user in a conversation.
- **MessagingService.mark_as_read**: Exposed the repository's mark_as_read functionality to the service layer.
- **Messaging Routes**: Updated the `/chat/<conversation_id>` route to trigger `mark_as_read` when a user enters a chat session.

### Security Rules
- **firestore.rules**: Created a production-ready security rules file that enforces:
  - Global authentication requirement for all collections.
  - Participant-only read/write access for conversations and their sub-collections (messages).
  - Immutability of the `participants` array in conversations after creation.
  - Sender identity verification for new messages.

### Testing
- **New Test File**: `tests/test_messaging_repository.py` added to verify the complex batch logic in `add_message`.
- **Updated Tests**: `tests/test_messaging.py` updated to include service-level `mark_as_read` verification.
- **Status**: All 6 messaging tests passing (along with pre-existing system tests).

## Deviations from Plan
- **Rule 2 - Missing Functionality**: Added a generic `match /{collection}/{document=**}` rule to `firestore.rules` to satisfy the requirement "Users must be authenticated to read or write any data" across the entire database while maintaining specific restrictions for messaging.

## Verification Results
### Automated Tests
- `pytest tests/test_messaging.py`: PASSED
- `pytest tests/test_messaging_repository.py`: PASSED

## Self-Check: PASSED
- [x] MessagingRepository and MessagingService support unread counts and last message tracking.
- [x] firestore.rules file exists with correct security logic.
- [x] All backend unit tests pass.
- [x] Commits made per task.
