from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client


class UserQueryService:
    """Service class for simple user query operations."""

    @staticmethod
    def get_users_by_ids(db: Client, user_ids: set[str]) -> dict[str, dict[str, Any]]:
        """Batch fetch users by their IDs."""
        if not user_ids:
            return {}

        user_refs = [db.collection("users").document(uid) for uid in user_ids]
        user_map = {}
        for u_snap in db.get_all(user_refs):
            if u_snap.exists:
                u_data = u_snap.to_dict() or {}
                uid = u_snap.id
                u_data["id"] = uid
                u_data["uid"] = uid
                user_map[uid] = u_data

        return user_map
