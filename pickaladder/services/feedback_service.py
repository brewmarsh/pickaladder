"""Service for handling user feedback."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from firebase_admin import firestore
from markupsafe import escape

from pickaladder.services.notification_service import NotificationService


class FeedbackService:
    """Service for handling user feedback."""

    @staticmethod
    def submit_feedback(
        db: firestore.client, user_id: str, feedback_type: str, message: str
    ) -> str:
        """Saves user feedback to the feedback collection."""
        # Sanitize message
        sanitized_message = str(escape(message))

        feedback_ref = db.collection("feedback").document()
        feedback_data = {
            "id": feedback_ref.id,
            "userId": user_id,
            "type": feedback_type,
            "message": sanitized_message,
            "status": "New",
            "createdAt": datetime.now(timezone.utc),
            "updatedAt": datetime.now(timezone.utc),
        }
        feedback_ref.set(feedback_data)
        return feedback_ref.id

    @staticmethod
    def get_all_feedback(db: firestore.client, limit: int = 50) -> list[dict[str, Any]]:
        """Returns all feedback ordered by createdAt DESC."""
        docs = (
            db.collection("feedback")
            .order_by("createdAt", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        return [doc.to_dict() for doc in docs]

    @staticmethod
    def update_feedback_status(
        db: firestore.client, feedback_id: str, status: str, admin_id: str
    ) -> bool:
        """Updates feedback status and notifies the user."""
        feedback_ref = db.collection("feedback").document(feedback_id)
        feedback_doc = feedback_ref.get()

        if not feedback_doc.exists:
            return False

        feedback_data = feedback_doc.to_dict()
        feedback_ref.update(
            {
                "status": status,
                "updatedAt": datetime.now(timezone.utc),
                "updatedBy": admin_id,
            }
        )

        # Notify the user
        user_id = feedback_data.get("userId")
        if user_id:
            title = "Feedback Update"
            body = f"The status of your feedback has been updated to '{status}'."
            NotificationService.send_to_user(
                user_id,
                title,
                body,
                {"type": "feedback_update", "feedback_id": feedback_id},
            )

        return True
