"""Service layer for tournament business logic."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from firebase_admin import firestore

from pickaladder.teams.services import TeamService
from pickaladder.user.helpers import smart_display_name
from pickaladder.utils import send_email

from .utils import get_tournament_standings

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client
    from google.cloud.firestore_v1.document import DocumentReference
    from google.cloud.firestore_v1.transaction import Transaction


class TournamentService:
    """Handles business logic and data access for tournaments."""

    # ... (_get_participant_refs and _resolve_participants remain same)

    @staticmethod
    def _get_invitable_players(
        db: Client, user_uid: str, current_participant_ids: set[str]
    ) -> list[dict[str, Any]]:
        """Internal helper to find invite candidates using modern FieldFilter."""
        user_ref = db.collection("users").document(user_uid)

        # Friends logic remains same...
        
        # Source B: Groups - Fixed with FieldFilter
        groups_query = (
            db.collection("groups")
            .where(filter=firestore.FieldFilter("members", "array_contains", user_ref))
            .stream()
        )
        
        # ... (Processing logic remains same)
        return invitable_users

    @staticmethod
    def list_tournaments(
        user_uid: str, db: Client | None = None
    ) -> list[dict[str, Any]]:
        """Fetch all tournaments for a user using FieldFilter."""
        if db is None:
            db = firestore.client()
        user_ref = db.collection("users").document(user_uid)

        owned = (
            db.collection("tournaments")
            .where(filter=firestore.FieldFilter("ownerRef", "==", user_ref))
            .stream()
        )
        participating = (
            db.collection("tournaments")
            .where(filter=firestore.FieldFilter("participant_ids", "array_contains", user_uid))
            .stream()
        )

        # ... (Result collection and date formatting logic remains same)
        return list(results.values())

    @staticmethod
    def update_tournament(
        tournament_id: str,
        user_uid: str,
        update_data: dict[str, Any],
        is_admin: bool = False,
        db: Client | None = None,
    ) -> None:
        """Update tournament details with ownership and admin overrides."""
        if db is None:
            db = firestore.client()
        ref = db.collection("tournaments").document(tournament_id)
        doc = cast(Any, ref.get())
        if not doc.exists:
            raise ValueError("Tournament not found.")

        data = doc.to_dict()
        owner_id = data.get("organizer_id") or (data.get("ownerRef").id if data.get("ownerRef") else None)

        # RESOLVED: Admin override from main branch
        if not is_admin and owner_id != user_uid:
            raise PermissionError("Unauthorized.")

        # Guard critical fields if matches exist (FieldFilter update)
        if any(f in update_data for f in ["matchType", "mode", "format"]):
            matches = (
                db.collection("matches")
                .where(filter=firestore.FieldFilter("tournamentId", "==", tournament_id))
                .limit(1)
                .stream()
            )
            if any(matches):
                for field in ["matchType", "mode", "format"]:
                    update_data.pop(field, None)

        ref.update(update_data)

    # ... (accept_team_partnership and other methods follow FieldFilter pattern)

class TournamentGenerator:
    """Utility class to generate tournament match pairings."""

    @staticmethod
    def generate_round_robin(participant_ids: list[str]) -> list[dict[str, Any]]:
        """Generate Round Robin pairings using fixed Circle Method rotation."""
        if not participant_ids or len(participant_ids) < 2:
            return []

        ids = list(participant_ids)
        if len(ids) % 2 != 0:
            ids.append(None)

        n = len(ids)
        pairings = []
        db = firestore.client()

        for _ in range(n - 1):
            for i in range(n // 2):
                p1, p2 = ids[i], ids[n - 1 - i]
                if p1 and p2:
                    pairings.append({
                        "player1Ref": db.collection("users").document(p1),
                        "player2Ref": db.collection("users").document(p2),
                        "matchType": "singles",
                        "status": "DRAFT",
                        "createdAt": firestore.SERVER_TIMESTAMP,
                        "participants": [p1, p2],
                    })
            # RESOLVED: Correct Circle Method rotation from main branch
            ids = [ids[0]] + [ids[-1]] + ids[1:-1]

        return pairings