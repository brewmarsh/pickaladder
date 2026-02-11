"""Service layer for admin-related operations."""

import datetime
from typing import Any

from firebase_admin import firestore


class AdminService:
    """Service class for admin-related operations."""

    @staticmethod
    def get_admin_stats(db: Any) -> dict[str, Any]:
        """Fetch high-level stats for the admin dashboard using efficient count aggregations."""
        # Total Users
        total_users = db.collection("users").count().get()[0][0].value

        # Active Tournaments (status != 'Completed')
        active_tournaments = (
            db.collection("tournaments")
            .where(filter=firestore.FieldFilter("status", "!=", "Completed"))
            .count()
            .get()[0][0]
            .value
        )

        # Recent Matches (last 24 hours)
        yesterday = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            days=1
        )
        recent_matches = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("createdAt", ">=", yesterday))
            .count()
            .get()[0][0]
            .value
        )

        return {
            "total_users": total_users,
            "active_tournaments": active_tournaments,
            "recent_matches": recent_matches,
        }

    @staticmethod
    def toggle_setting(db: Any, setting_key: str) -> bool:
        """Toggle a boolean setting in the Firestore 'settings' collection."""
        setting_ref = db.collection("settings").document(setting_key)
        setting = setting_ref.get()
        current_value = (
            setting.to_dict().get("value", False) if setting.exists else False
        )
        not_current_value = not current_value
        setting_ref.set({"value": not_current_value})
        return not_current_value

    @staticmethod
    def delete_user(db: Any, user_id: str) -> None:
        """Delete a user from Firebase Auth and Firestore."""
        from firebase_admin import auth  # noqa: PLC0415

        # Delete from Firebase Auth
        auth.delete_user(user_id)
        # Delete from Firestore
        db.collection("users").document(user_id).delete()

    @staticmethod
    def promote_user(db: Any, user_id: str) -> str:
        """Promote a user to admin status in Firestore."""
        user_ref = db.collection("users").document(user_id)
        user_ref.update({"isAdmin": True})
        return user_ref.get().to_dict().get("username", "user")

    @staticmethod
    def verify_user(db: Any, user_id: str) -> None:
        """Manually verify a user's email in Auth and Firestore."""
        from firebase_admin import auth  # noqa: PLC0415

        auth.update_user(user_id, email_verified=True)
        user_ref = db.collection("users").document(user_id)
        user_ref.update({"email_verified": True})
