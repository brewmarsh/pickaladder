from __future__ import annotations
from typing import TYPE_CHECKING, Any, cast
from firebase_admin import firestore

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client

class MatchCandidateService:
    @staticmethod
    def get_candidate_player_ids(
        db: Client,
        user_id: str,
        group_id: str | None = None,
        tournament_id: str | None = None,
        include_user: bool = False,
    ) -> set[str]:
        """Fetch a set of valid opponent IDs for a user."""
        candidate_ids: set[str] = {user_id}
        if tournament_id:
            candidate_ids.update(
                MatchCandidateService._get_tournament_participants(db, tournament_id)
            )
        elif group_id:
            candidate_ids.update(MatchCandidateService._get_group_candidates(db, group_id))
        else:
            candidate_ids.update(MatchCandidateService._get_default_candidates(db, user_id))

        if not include_user:
            candidate_ids.discard(user_id)
        return candidate_ids

    @staticmethod
    def _get_tournament_participants(db: Client, tournament_id: str) -> list[str]:
        """Fetch participant IDs for a tournament."""
        doc = db.collection("tournaments").document(tournament_id).get()
        return (doc.to_dict() or {}).get("participant_ids", []) if doc.exists else []

    @staticmethod
    def _get_group_candidates(db: Client, group_id: str) -> set[str]:
        """Fetch group members and invited users for a group."""
        candidates: set[str] = set()
        group_doc = db.collection("groups").document(group_id).get()
        if group_doc.exists:
            for ref in (group_doc.to_dict() or {}).get("members", []):
                candidates.add(ref.id)

        invites = (
            db.collection("group_invites")
            .where(filter=firestore.FieldFilter("group_id", "==", group_id))
            .where(filter=firestore.FieldFilter("used", "==", False))
            .stream()
        )
        emails = [
            (doc.to_dict() or {}).get("email")
            for doc in invites
            if (doc.to_dict() or {}).get("email")
        ]
        if emails:
            for i in range(0, len(emails), 30):
                users = (
                    db.collection("users")
                    .where(
                        filter=firestore.FieldFilter("email", "in", emails[i : i + 30])
                    )
                    .stream()
                )
                candidates.update(u.id for u in users)
        return candidates

    @staticmethod
    def _get_default_candidates(db: Client, user_id: str) -> set[str]:
        """Fetch friends and personal invitees for a user."""
        candidates: set[str] = set()
        friends = (
            db.collection("users").document(user_id).collection("friends").stream()
        )
        candidates.update(
            f.id
            for f in friends
            if (f.to_dict() or {}).get("status") in ["accepted", "pending"]
        )

        invites = (
            db.collection("group_invites")
            .where(filter=firestore.FieldFilter("inviter_id", "==", user_id))
            .stream()
        )
        emails = list(
            {
                (doc.to_dict() or {}).get("email")
                for doc in invites
                if (doc.to_dict() or {}).get("email")
            }
        )
        if emails:
            for i in range(0, len(emails), 10):
                users = (
                    db.collection("users")
                    .where(
                        filter=firestore.FieldFilter("email", "in", emails[i : i + 10])
                    )
                    .stream()
                )
                candidates.update(u.id for u in users)
        return candidates
