from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from .base import TournamentBase

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client


class TournamentTeams(TournamentBase):
    """Handles team logic for tournaments."""

    @staticmethod
    def register_team(
        t_id: str, p1: str, p2: str | None, name: str, db: Client | None = None
    ) -> str:
        """Register a team in the tournament teams sub-collection."""
        from firebase_admin import firestore

        from pickaladder.teams.services import TeamService

        if db is None:
            db = firestore.client()
        d = {
            "p1_uid": p1,
            "p2_uid": p2,
            "team_name": name,
            "status": "PENDING",
            "createdAt": firestore.SERVER_TIMESTAMP,
        }
        if p2:
            d["team_id"] = TeamService.get_or_create_team(db, p1, p2)
        ref = db.collection("tournaments").document(t_id).collection("teams").document()
        ref.set(d)
        return str(ref.id)

    @staticmethod
    def accept_team_partnership(t_id: str, uid: str, db: Client | None = None) -> bool:
        """Accept a team partnership invitation."""
        from firebase_admin import firestore

        from pickaladder.teams.services import TeamService

        if db is None:
            db = firestore.client()
        query = (
            db.collection("tournaments")
            .document(t_id)
            .collection("teams")
            .where(filter=firestore.FieldFilter("p2_uid", "==", uid))
            .where(filter=firestore.FieldFilter("status", "==", "PENDING"))
            .stream()
        )
        updated = False
        for doc in query:
            d = doc.to_dict()
            team_id = TeamService.get_or_create_team(db, d["p1_uid"], uid)
            doc.reference.update({"status": "CONFIRMED", "team_id": team_id})
            TournamentTeams._sync_team_participants(
                db, t_id, d["p1_uid"], uid, d.get("team_name")
            )
            updated = True
        return updated

    @staticmethod
    def _sync_team_participants(
        db: Client, t_id: str, p1: str, p2: str, name: str | None
    ) -> None:
        """Ensure both team members are in the tournament participants."""
        from firebase_admin import firestore

        ref = db.collection("tournaments").document(t_id)
        snap = cast(Any, ref.get())
        ids = (snap.to_dict() or {}).get("participant_ids", [])
        new_ids, new_ps = [], []
        for u in [p1, p2]:
            if u not in ids:
                new_ids.append(u)
                new_ps.append(
                    {
                        "userRef": db.collection("users").document(u),
                        "status": "accepted",
                        "team_name": name,
                    }
                )
        if new_ps:
            ref.update(
                {
                    "participants": firestore.ArrayUnion(new_ps),
                    "participant_ids": firestore.ArrayUnion(new_ids),
                }
            )

    @staticmethod
    def claim_team_partnership(
        t_id: str, team_id: str, uid: str, db: Client | None = None
    ) -> bool:
        """Join a placeholder team via an invite link."""
        from firebase_admin import firestore

        from pickaladder.teams.services import TeamService

        if db is None:
            db = firestore.client()
        ref = (
            db.collection("tournaments")
            .document(t_id)
            .collection("teams")
            .document(team_id)
        )
        snap = cast(Any, ref.get())
        if (
            not snap.exists
            or (d := snap.to_dict()).get("p2_uid")
            or d.get("p1_uid") == uid
        ):
            return False
        team_id_global = TeamService.get_or_create_team(db, d["p1_uid"], uid)
        ref.update({"p2_uid": uid, "status": "CONFIRMED", "team_id": team_id_global})
        TournamentTeams._sync_team_participants(
            db, t_id, d["p1_uid"], uid, d.get("team_name")
        )
        return True
