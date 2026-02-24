from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from pickaladder.user.helpers import smart_display_name

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client
    from google.cloud.firestore_v1.document import DocumentReference


class TournamentBase:
    """Base class with shared helpers for tournament services."""

    @staticmethod
    def _get_tournament_owner_id(data: dict[str, Any]) -> str | None:
        """Resolve organizer/owner ID from tournament data."""
        o_id = data.get("organizer_id")
        if o_id:
            return cast(str, o_id)
        return data["ownerRef"].id if data.get("ownerRef") else None

    @staticmethod
    def _get_participant_refs(
        db: Client, participant_objs: list[dict[str, Any]]
    ) -> list[DocumentReference]:
        """Extract user references from participant objects."""
        user_refs = []
        for obj in participant_objs:
            if not obj:
                continue
            if obj.get("userRef"):
                user_refs.append(obj["userRef"])
            elif obj.get("user_id"):
                user_refs.append(db.collection("users").document(obj["user_id"]))
        return user_refs

    @staticmethod
    def _resolve_single_participant(
        obj: dict[str, Any], users_map: dict[str, dict[str, Any]]
    ) -> dict[str, Any] | None:
        """Format a single participant with user data."""
        u_ref = obj.get("userRef")
        uid = u_ref.id if u_ref else obj.get("user_id")
        if uid and uid in users_map:
            u_data = users_map[uid]
            return {
                "user": u_data,
                "status": obj.get("status", "pending"),
                "display_name": smart_display_name(u_data),
                "team_name": obj.get("team_name"),
            }
        return None

    @staticmethod
    def _resolve_participants(
        db: Client, participant_objs: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Internal helper to resolve participant user data."""
        if not participant_objs:
            return []
        refs = TournamentBase._get_participant_refs(db, participant_objs)
        if not refs:
            return []
        u_docs = cast(list[Any], db.get_all(refs))
        u_map = {
            doc.id: {**(doc.to_dict() or {}), "id": doc.id}
            for doc in u_docs
            if doc.exists
        }
        participants = []
        for obj in participant_objs:
            if not obj:
                continue
            p = TournamentBase._resolve_single_participant(obj, u_map)
            if p:
                participants.append(p)
        return participants
