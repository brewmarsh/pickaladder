"""Service layer for admin-related operations."""

from typing import Any, Dict, List  # noqa: UP035

from firebase_admin import auth, firestore


class AdminService:
    """Service class for admin-related operations."""

    @staticmethod
    def build_friend_graph(db: Any) -> Dict[str, List[Dict[str, Any]]]:  # noqa: UP006
        """Build a dictionary of nodes and edges for a friendship graph."""
        users = db.collection("users").stream()
        nodes = []
        edges = []
        for user in users:
            user_data = user.to_dict()
            nodes.append({"id": user.id, "label": user_data.get("username", user.id)})
            # Fetch friends for this user
            friends_query = (
                db.collection("users")
                .document(user.id)
                .collection("friends")
                .where(filter=firestore.FieldFilter("status", "==", "accepted"))
                .stream()
            )
            for friend in friends_query:
                # Add edge only once
                if user.id < friend.id:
                    edges.append({"from": user.id, "to": friend.id})
        return {"nodes": nodes, "edges": edges}

    @staticmethod
    def toggle_setting(db: Any, setting_key: str) -> bool:
        """Toggle a boolean setting in the Firestore 'settings' collection."""
        setting_ref = db.collection("settings").document(setting_key)
        setting = setting_ref.get()
        current_value = (
            setting.to_dict().get("value", False) if setting.exists else False
        )
        new_value = not current_value
        setting_ref.set({"value": new_value})
        return new_value

    @staticmethod
    def delete_user(db: Any, user_id: str) -> None:
        """Delete a user from Firebase Auth and Firestore."""
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
        auth.update_user(user_id, email_verified=True)
        user_ref = db.collection("users").document(user_id)
        user_ref.update({"email_verified": True})

    @staticmethod
    def get_admin_stats(db: Any) -> Dict[str, Any]:
        """Get high-level stats for the admin dashboard."""
        from datetime import datetime, timedelta, timezone

        # User Count
        total_users = len(db.collection("users").get())

        # Active Tournaments
        active_tournaments = len(
            db.collection("tournaments")
            .where(filter=firestore.FieldFilter("status", "!=", "Completed"))
            .get()
        )

        # Recent Matches (Since yesterday at midnight)
        yesterday = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=1)
        recent_matches = len(
            db.collection("matches")
            .where(filter=firestore.FieldFilter("matchDate", ">=", yesterday))
            .get()
        )

        return {
            "total_users": total_users,
            "active_tournaments": active_tournaments,
            "recent_matches": recent_matches,
        }
