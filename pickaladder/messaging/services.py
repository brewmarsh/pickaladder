"""Service layer for messaging operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from firebase_admin import firestore

from .repository import MessagingRepository

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client


class MessagingService:
    """Handles business logic for player messaging."""

    @staticmethod
    def get_or_create_conversation(db: Client, user_id1: str, user_id2: str) -> str:
        """Finds or initializes a 1-on-1 conversation."""
        existing = MessagingRepository.find_direct_conversation(db, user_id1, user_id2)
        if existing:
            return existing["id"]

        # Create new
        payload = {
            "participants": [user_id1, user_id2],
            "lastMessage": "",
            "updatedAt": firestore.SERVER_TIMESTAMP,
            "unreadCount": {user_id1: 0, user_id2: 0},
        }
        return MessagingRepository.create(db, payload)

    @staticmethod
    def get_or_create_group_announcement(
        db: Client,
        group_id: str,
        owner_id: str,
        member_ids: list[str],
    ) -> str:
        """Finds or initializes a group announcement channel."""
        query = (
            db.collection(MessagingRepository.COLLECTION_NAME)
            .where(filter=firestore.FieldFilter("groupId", "==", group_id))
            .where(filter=firestore.FieldFilter("type", "==", "group_announcement"))
            .limit(1)
        )

        docs = list(query.stream())
        if docs:
            return docs[0].id

        # Create new
        payload = {
            "participants": member_ids,
            "type": "group_announcement",
            "ownerId": owner_id,
            "groupId": group_id,
            "lastMessage": "",
            "updatedAt": firestore.SERVER_TIMESTAMP,
            "unreadCount": dict.fromkeys(member_ids, 0),
        }
        return MessagingRepository.create(db, payload)

    @staticmethod
    def send_message(
        db: Client,
        conversation_id: str,
        sender_id: str,
        content: str,
    ) -> str:
        """Sends a message in a conversation."""
        # Note: In a production app, we would use Firestore Security Rules
        # or a server-side check here to ensure the sender is a participant.

        msg_data = {"senderId": sender_id, "content": content, "read": False}
        return MessagingRepository.add_message(db, conversation_id, msg_data)

    @staticmethod
    def mark_as_read(db: Client, conversation_id: str, user_id: str) -> None:
        """Resets the unread count for that user in the conversation."""
        MessagingRepository.mark_as_read(db, conversation_id, user_id)

    @staticmethod
    def get_inbox(db: Client, user_id: str) -> list[dict[str, Any]]:
        """Retrieves the user's conversation list with enriched participant names."""
        conversations = MessagingRepository.get_user_conversations(db, user_id)

        if not conversations:
            return []

        # ⚡ Bolt Optimization:
        # What: Replaced sequential `get_by_id` calls with a single `db.get_all()` cross-collection batch fetch.
        # Why: Resolves an N+1 query bottleneck where each conversation required an independent network round-trip.
        # Impact: Reduces database latency from O(N) to exactly 1 request for retrieving inbox metadata.
        refs = []
        for conv in conversations:
            if conv.get("type") == "group_announcement":
                refs.append(db.collection("groups").document(conv["groupId"]))
            else:
                other_uid = next(
                    (p for p in conv["participants"] if p != user_id),
                    user_id,
                )
                refs.append(db.collection("users").document(other_uid))

        docs = db.get_all(refs)
        doc_map = {doc.reference: doc for doc in docs}

        for conv in conversations:
            if conv.get("type") == "group_announcement":
                ref = db.collection("groups").document(conv["groupId"])
                doc = doc_map.get(ref)
                if doc and doc.exists:
                    group_data = doc.to_dict() or {}
                    group_name = group_data.get("name", "Unknown Group")
                else:
                    group_name = "Deleted Group"
                conv["display_name"] = f"{group_name} (Announcements)"
                conv["display_avatar"] = None
            else:
                other_uid = next(
                    (p for p in conv["participants"] if p != user_id),
                    user_id,
                )
                ref = db.collection("users").document(other_uid)
                doc = doc_map.get(ref)
                if doc and doc.exists:
                    user_data = doc.to_dict() or {}
                    conv["display_name"] = user_data.get("username", "Unknown User")
                    conv["display_avatar"] = user_data.get("profilePictureUrl")
                else:
                    conv["display_name"] = "Deleted User"
                    conv["display_avatar"] = None

        return conversations

    @staticmethod
    def get_total_unread_count(db: Client, user_id: str) -> int:
        """Sum the unread counts for a user across all their conversations."""
        conversations = MessagingRepository.get_user_conversations(db, user_id)
        total = 0
        for conv in conversations:
            unread_dict = conv.get("unreadCount", {})
            total += unread_dict.get(user_id, 0)
        return total
