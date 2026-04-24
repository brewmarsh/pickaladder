# Plan: 17-01: Messaging Infrastructure & Direct Chat

**Goal:** Implement the core messaging models and direct player-to-player chat functionality.

## Tasks
1. [ ] Define **Conversation** and **Message** data models.
    - Conversation: `participants` (UID array), `lastMessage`, `updatedAt`.
    - Message: `senderId`, `content`, `timestamp`.
2. [ ] Implement `MessagingService`:
    - `get_or_create_conversation(user_id1, user_id2)`
    - `send_message(conversation_id, sender_id, content)`
    - `get_messages(conversation_id, limit)`
3. [ ] Build the **Messaging Blueprint**:
    - `/messages`: Inbox view.
    - `/messages/chat/<conversation_id>`: Individual chat view.
4. [ ] Create Frontend Components:
    - Chat bubble styling (Volt/Dark theme).
    - Auto-scroll to bottom.
    - Simple long-polling or Firestore listener (client-side) for real-time updates.

## Technical Details
- **Firestore Schema:**
    - `/conversations/{cid}`
    - `/conversations/{cid}/messages/{mid}`
- **Security:** Security Rules must enforce that only participants can read/write messages in a conversation.

## Success Criteria
- [ ] Users can start a chat with a friend from their profile.
- [ ] Messages are delivered and displayed in chronological order.
- [ ] Inbox correctly shows the latest message and timestamp for each conversation.
