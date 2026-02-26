from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from pickaladder.user.helpers import smart_display_name

from .base import TournamentBase

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client
    from google.cloud.firestore_v1.document import DocumentReference
    from google.cloud.firestore_v1.transaction import Transaction


class TournamentInvites(TournamentBase):
    """Handles invitations logic for tournaments."""

    @staticmethod
    def _get_invitable_ids(db: Client, user_uid: str) -> set[str]:
        """Fetch all friend and group member IDs for a user."""
<<<<<<< HEAD

=======
>>>>>>> 5b6fedc53d3e2c69d264664019f19c0939aa07ca
        user_ref = db.collection("users").document(user_uid)
        f_ids = {doc.id for doc in user_ref.collection("friends").stream()}
        g_ids = set()
        groups = (
            db.collection("groups")
            .where(filter=firestore.FieldFilter("members", "array_contains", user_ref))
            .stream()
        )
        for doc in groups:
            members = cast(dict[str, Any], doc.to_dict() or {}).get("members")
            if members:
                for m_ref in members:
                    g_ids.add(m_ref.id)
        return (f_ids | g_ids) - {str(user_uid)}

    @staticmethod
    def _get_invitable_players(
        db: Client, user_uid: str, current_ids: set[str]
    ) -> list[dict[str, Any]]:
        """Internal helper to find invite candidates."""
        final_ids = TournamentInvites._get_invitable_ids(db, user_uid) - current_ids
        invitable = []
        if final_ids:
            u_refs = [db.collection("users").document(uid) for uid in final_ids]
            u_docs = cast(list[Any], db.get_all(u_refs))
            for doc in u_docs:
                if doc.exists and (data := doc.to_dict()):
                    data["id"] = doc.id
                    invitable.append(data)
        invitable.sort(key=lambda u: smart_display_name(u).lower())
        return invitable

    @staticmethod
    def invite_player(
        t_id: str, uid: str, invited_uid: str, db: Client | None = None
    ) -> None:
        """Invite a single player."""
        from pickaladder.tournament.services import firestore

        if db is None:
            db = firestore.client()
        invited_ref = db.collection("users").document(invited_uid)
        db.collection("tournaments").document(t_id).update(
            {
                "participants": firestore.ArrayUnion(
                    [
                        {
                            "userRef": invited_ref,
                            "status": "pending",
                            "team_name": None,
                        }
                    ]
                ),
                "participant_ids": firestore.ArrayUnion([invited_uid]),
            }
        )

    @staticmethod
    def _validate_group_invite(
        db: Client, t_data: dict[str, Any], g_id: str, uid: str
    ) -> list[Any]:
        """Validate permissions and return group member references."""
        if TournamentInvites._get_tournament_owner_id(t_data) != uid:
            raise PermissionError("Unauthorized.")
        doc = cast(Any, db.collection("groups").document(g_id).get())
        if not doc.exists:
            raise ValueError("Group not found")
        refs = (doc.to_dict() or {}).get("members", [])
        if not any(m.id == uid for m in refs):
            raise PermissionError(
                "You can only invite members from groups you belong to."
            )
        return cast(list[Any], refs)

    @staticmethod
    def _prepare_group_invites(
        m_docs: list[DocumentSnapshot], current_ids: set[str]
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Filter group members and prepare invite objects."""
        new_p, new_ids = [], []
        for m in m_docs:
            if not m.exists or m.id in current_ids:
                continue
            d = m.to_dict() or {}
            p = {"userRef": m.reference, "status": "pending", "team_name": None}
            if d.get("is_ghost") and d.get("email"):
                p["email"] = d.get("email")
            new_p.append(p)
            new_ids.append(m.id)
        return new_p, new_ids

    @staticmethod
    def invite_group(t_id: str, g_id: str, uid: str, db: Client | None = None) -> int:
        """Invite all members of a group. Returns count of new invites."""
        from pickaladder.tournament.services import firestore

        if db is None:
            db = firestore.client()
        ref = db.collection("tournaments").document(t_id)
        doc = cast(Any, ref.get())
        if not doc.exists:
            raise ValueError("Tournament not found")
        t_data = cast(dict[str, Any], doc.to_dict())
        member_refs = TournamentInvites._validate_group_invite(db, t_data, g_id, uid)
        new_p, n_ids = TournamentInvites._prepare_group_invites(
            cast(list[Any], db.get_all(member_refs)),
            set(t_data.get("participant_ids", [])),
        )
        if new_p:
            batch = db.batch()
            batch.update(
                ref,
                {
                    "participants": firestore.ArrayUnion(new_p),
                    "participant_ids": firestore.ArrayUnion(n_ids),
                },
            )
            batch.commit()
        return len(new_p)

    @staticmethod
    def _update_status(parts: list[dict[str, Any]], uid: str, status: str) -> bool:
        """Update status of a participant in the list."""
        for p in parts:
            if not p:
                continue
            r = p.get("userRef")
            if r is not None and hasattr(r, "id"):
                p_uid = str(r.id)
            else:
                p_uid = str(p.get("user_id"))
            if p_uid == str(uid) and p.get("status") == "pending":
                p["status"] = status
                return True
        return False

    @staticmethod
    def accept_invite(t_id: str, uid: str, db: Client | None = None) -> bool:
        """Accept invite via transaction."""
        from pickaladder.tournament.services import firestore

        if db is None:
            db = firestore.client()
        ref = db.collection("tournaments").document(t_id)

        @firestore.transactional
        def _tx(tx: Transaction, t_ref: DocumentReference) -> bool:
            snap = cast(Any, t_ref.get(transaction=tx))
            if not snap.exists:
                return False
            parts = snap.get("participants")
            if TournamentInvites._update_status(parts, uid, "accepted"):
                tx.update(t_ref, {"participants": parts})
                return True
            return False

        return _tx(db.transaction(), ref)

    @staticmethod
    def decline_invite(t_id: str, uid: str, db: Client | None = None) -> bool:
        """Decline invite via transaction."""
        from pickaladder.tournament.services import firestore

        if db is None:
            db = firestore.client()
        ref = db.collection("tournaments").document(t_id)

        @firestore.transactional
        def _tx(tx: Transaction, t_ref: DocumentReference) -> bool:
            snap = cast(Any, t_ref.get(transaction=tx))
            if not snap.exists:
                return False
            parts, ids = snap.get("participants"), snap.get("participant_ids")
            new_p = [
                p
                for p in parts
                if p
                and not (
                    (
                        getattr(p.get("userRef"), "id", p.get("user_id"))
                        if p.get("userRef")
                        else p.get("user_id")
                    )
                    == uid
                    and p.get("status") == "pending"
                )
            ]
            if len(new_p) < len(parts):
                new_ids = [i for i in ids if i != uid]
                tx.update(t_ref, {"participants": new_p, "participant_ids": new_ids})
                return True
            return False

        return _tx(db.transaction(), ref)
