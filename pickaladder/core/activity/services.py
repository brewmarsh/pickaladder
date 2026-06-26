"""Service layer for social activity tracking."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from firebase_admin import firestore

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client


class ActivityService:
    """Handles logging and retrieval of community events."""

    COLLECTION_NAME = "activities"

    @staticmethod
    def log_activity(
        db: Client,
        user_id: str,
        activity_type: str,
        data: dict[str, Any],
    ) -> str:
        """Records a new event in the global activity collection."""
        activity_ref = db.collection(ActivityService.COLLECTION_NAME).document()
        payload = {
            "userId": user_id,
            "type": activity_type,
            "data": data,
            "timestamp": firestore.SERVER_TIMESTAMP,
            "reactions": [],
        }
        activity_ref.set(payload)
        return activity_ref.id

    @staticmethod
    def get_global_feed(db: Client, limit: int = 20) -> list[dict[str, Any]]:
        """Retrieves recent activities enriched with user data."""
        from pickaladder.user.services import UserService

        query = (
            db.collection(ActivityService.COLLECTION_NAME)
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )

        activities = []
        for doc in query.stream():
            data = doc.to_dict()
            data["id"] = doc.id

            # Enrich with user profile
            user = UserService.get_user_by_id(db, data["userId"])
            data["user"] = user or {"username": "Unknown", "id": data["userId"]}

            activities.append(data)

        return activities

    @staticmethod
    def toggle_reaction(
        db: Client,
        activity_id: str,
        user_id: str,
        reaction_type: str = "CHEER",
    ) -> list[dict[str, Any]]:
        """Adds or removes a user's reaction from an activity."""
        activity_ref = db.collection(ActivityService.COLLECTION_NAME).document(
            activity_id,
        )
        doc = activity_ref.get()
        if not doc.exists:
            return []

        data = doc.to_dict()
        reactions = data.get("reactions", [])

        # Check if user already reacted
        existing = next((r for r in reactions if r["userId"] == user_id), None)

        if existing:
            # Remove it
            activity_ref.update({"reactions": firestore.ArrayRemove([existing])})
            reactions.remove(existing)
        else:
            # Add it
            new_reaction = {
                "userId": user_id,
                "type": reaction_type,
                "timestamp": firestore.SERVER_TIMESTAMP,  # Tricky for local list return
            }
            activity_ref.update({"reactions": firestore.ArrayUnion([new_reaction])})
            reactions.append(new_reaction)

        return reactions
