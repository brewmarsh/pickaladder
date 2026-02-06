"""Service layer for tournament business logic."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from firebase_admin import firestore
from flask import current_app

from pickaladder.user.utils import smart_display_name
from pickaladder.utils import send_email

from .utils import get_tournament_standings

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client
    from google.cloud.firestore_v1.document import DocumentReference
    from google.cloud.firestore_v1.transaction import Transaction


class TournamentService:
    """Handles business logic and data access for tournaments."""

    @staticmethod
    def _resolve_participants(
        db: Client, participant_objs: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Internal helper to resolve participant user data."""
        if not participant_objs:
            return []

        user_refs = []
        for obj in participant_objs:
            if not obj:
                continue
            if obj.get("userRef"):
                user_refs.append(obj["userRef"])
            elif obj.get("user_id"):
                user_refs.append(db.collection("users").document(obj["user_id"]))

        if not user_refs:
            return []

        user_docs = cast(list[Any], db.get_all(user_refs))
        users_map = {
            doc.id: {**(doc.to_dict() or {}), "id": doc.id}
            for doc in user_docs
            if doc.exists
        }

        participants = []
        for obj in participant_objs:
            if not obj:
                continue
            user_ref = obj.get("userRef")
            uid = user_ref.id if user_ref else obj.get("user_id")
            if uid and uid in users_map:
                u_data = users_map[uid]
                participants.append(
                    {
                        "user": u_data,
                        "status": obj.get("status", "pending"),
                        "display_name": smart_display_name(u_data),
                        "team_name": obj.get("team_name"),
                    }
                )
        return participants

    @staticmethod
    def _get_invitable_players(
        db: Client, user_uid: str, current_participant_ids: set[str]
    ) -> list[dict[str, Any]]:
        """Internal helper to find invite candidates."""
        user_ref = db.collection("users").document(user_uid)

        # Source A: Friends
        friends_query = user_ref.collection("friends").stream()
        friend_ids = {doc.id for doc in friends_query}

        # Source B: Groups
        groups_query = (
            db.collection("groups")
            .where(filter=firestore.FieldFilter("members", "array_contains", user_ref))
            .stream()
        )
        group_member_ids = set()
        for group_doc in groups_query:
            g_data = group_doc.to_dict()
            if g_data and "members" in g_data:
                for m_ref in g_data["members"]:
                    group_member_ids.add(m_ref.id)

        all_ids = {str(uid) for uid in (friend_ids | group_member_ids)}
        all_ids.discard(str(user_uid))
        final_ids = all_ids - current_participant_ids

        invitable_users = []
        if final_ids:
            u_refs = [db.collection("users").document(uid) for uid in final_ids]
            u_docs = cast(list[Any], db.get_all(u_refs))
            for u_doc in u_docs:
                if u_doc.exists