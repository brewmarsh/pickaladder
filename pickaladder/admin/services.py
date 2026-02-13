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
    def delete_user_data(db: Any, uid: str) -> None:
        """Delete a user from Firestore and Firebase Auth."""
        from firebase_admin import auth  # noqa: PLC0415

        # Delete from Firestore
        db.collection("users").document(uid).delete()
        # Delete from Firebase Auth
        try:
            auth.delete_user(uid)
        except Exception:  # nosec B110
            # If user not found in Auth, we still want to proceed
            pass

    @staticmethod
    def build_friend_graph(db: Any) -> dict[str, Any]:
        """Build a dictionary representing the social graph of users and friendships."""
        users_stream = db.collection("users").stream()
        nodes = []
        user_ids = set()

        for user_doc in users_stream:
            data = user_doc.to_dict()
            nodes.append(
                {"id": user_doc.id, "label": data.get("username") or user_doc.id}
            )
            user_ids.add(user_doc.id)

        edges = []
        # Optimization: We only need to iterate over users once.
        # Friendships are reciprocal.
        for uid in user_ids:
            friends_stream = (
                db.collection("users")
                .document(uid)
                .collection("friends")
                .where(filter=firestore.FieldFilter("status", "==", "accepted"))
                .stream()
            )
            for friend_doc in friends_stream:
                if uid < friend_doc.id:  # Avoid duplicate edges
                    edges.append({"from": uid, "to": friend_doc.id})

        return {"nodes": nodes, "edges": edges}

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
