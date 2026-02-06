"""Service layer for user business logic."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from firebase_admin import firestore

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client

logger = logging.getLogger(__name__)


class UserService:
    """Handles business logic and data access for users."""

    @staticmethod
    def merge_users(source_uid: str, target_uid: str, db: Client | None = None) -> bool:
        """Merge source user into target user and archive source."""
        if source_uid == target_uid:
            raise ValueError("Source and target users must be different.")

        if db is None:
            db = cast("Client", firestore.client())

        source_ref = db.collection("users").document(source_uid)
        target_ref = db.collection("users").document(target_uid)

        source_doc = cast("DocumentSnapshot", source_ref.get())
        target_doc = cast("DocumentSnapshot", target_ref.get())

        if not source_doc.exists:
            raise ValueError(f"Source user {source_uid} not found.")
        if not target_doc.exists:
            raise ValueError(f"Target user {target_uid} not found.")

        # TODO: Implement migration logic

        return True
