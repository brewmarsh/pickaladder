"""Repository for messaging data access."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from firebase_admin import firestore

from pickaladder.base.repository import BaseRepository

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client


DIRECT_CONVERSATION_PARTICIPANTS = 2


class MessagingRepository(BaseRepository):
    """Handles persistence for conversations and messages."""

    COLLECTION_NAME = "conversations"

    @classmethod
    def get_user_conversations(cls, db: Client, user_id: str) -> list[dict[str, Any]]:
        """Fetch all conversations where the user is a participant."""
        query = (
            db.collection(cls.COLLECTION_NAME)
            .where(
                filter=firestore.FieldFilter("participants", "array_contains", user_id),
            )
            .order_by("updatedAt", direction=firestore.Query.DESCENDING)
        )

        return [doc.to_dict() | {"id": doc.id} for doc in query.stream()]

    @classmethod
    def find_direct_conversation(
        cls,
        db: Client,
        user_id1: str,
        user_id2: str,
    ) -> dict[str, Any] | None:
        """Find an existing 1-on-1 conversation between two users."""
        # Note: Firestore doesn't support array-equals with order-independence easily.
        # We query for conversations where user1 is a participant and filter in-memory for user2.
        query = db.collection(cls.COLLECTION_NAME).where(
            filter=firestore.FieldFilter("participants", "array_contains", user_id1),
        )

        for doc in query.stream():
            data = doc.to_dict()
            parts = data.get("participants", [])
            if len(parts) == DIRECT_CONVERSATION_PARTICIPANTS and user_id2 in parts:
                return data | {"id": doc.id}

        return None

    @classmethod
    def get_messages(
        cls,
        db: Client,
        conversation_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Fetch message history for a conversation."""
        query = (
            db.collection(cls.COLLECTION_NAME)
            .document(conversation_id)
            .collection("messages")
            .order_by("timestamp", direction=firestore.Query.ASCENDING)
            .limit(limit)
        )

        return [doc.to_dict() | {"id": doc.id} for doc in query.stream()]

    @classmethod
    def add_message(
        cls,
        db: Client,
        conversation_id: str,
        message_data: dict[str, Any],
    ) -> str:
        """Append a message to a conversation and update metadata."""
        conv_ref = db.collection(cls.COLLECTION_NAME).document(conversation_id)

        # Fetch participants to handle unread counts
        conv_doc = conv_ref.get()
        participants = (
            conv_doc.to_dict().get("participants", []) if conv_doc.exists else []
        )

        sender_id = message_data.get("senderId")

        msg_ref = conv_ref.collection("messages").document()

        batch = db.batch()
        batch.set(msg_ref, message_data | {"timestamp": firestore.SERVER_TIMESTAMP})

        updates = {
            "lastMessage": message_data.get("content", "")[:100],
            "lastMessageSenderId": sender_id,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        }

        for participant_id in participants:
            if participant_id != sender_id:
                updates[f"unreadCount.{participant_id}"] = firestore.Increment(1)

        batch.update(conv_ref, updates)
        batch.commit()

        return msg_ref.id

    @classmethod
    def mark_as_read(cls, db: Client, conversation_id: str, user_id: str) -> None:
        """Reset unread count for a user in a conversation."""
        conv_ref = db.collection(cls.COLLECTION_NAME).document(conversation_id)
        conv_ref.update({f"unreadCount.{user_id}": 0})
