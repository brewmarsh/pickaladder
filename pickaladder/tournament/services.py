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

# Constants from main branch
MIN_PARTICIPANTS = 2


class TournamentGenerator:
    """Implements tournament generation logic (e.g., Round Robin)."""

    @staticmethod
    def generate_round_robin(participant_ids: list[str]) -> list[dict[str, Any]]:
        """Generate Round Robin pairings using the Circle Method."""
        if len(participant_ids) < MIN_PARTICIPANTS:
            return []

        ids: list[str | None] = list(participant_ids)
        if len(ids) % 2 != 0:
            ids.append(None)  # Bye

        n = len(ids)
        pairings = []
        db = firestore.client()

        for _ in range(n - 1):
            for i in range(n // 2):
                p1 = ids[i]
                p2 = ids[n - 1 - i]
                if p1 and p2:
                    pairings.append({
                        "player1Ref": db.collection("users").document(p1),
                        "player2Ref": db.collection("users").document(p2),
                        "participants": [p1, p2],
                        "matchType": "singles",
                        "status": "DRAFT",
                        "createdAt": firestore.SERVER_TIMESTAMP,
                    })
            # Rotate
            ids.insert(1, ids.pop())

        return pairings


class TournamentService:
    """Handles business logic and data access for tournaments."""

    # ... (Internal helpers _get_participant_refs and _resolve_participants remain same)

    @staticmethod
    def list_tournaments(user_uid: str, db: Client | None = None) -> list[dict[str, Any]]:
        """Fetch all tournaments for a user with updated FieldFilter syntax."""
        if db is None:
            db = firestore.client()
        user_ref = db.collection("users").document(user_uid)

        # Using modern FieldFilter syntax from fix branch to avoid UserWarnings
        owned = db.collection("tournaments").where(
            filter=firestore.FieldFilter("ownerRef", "==", user_ref)
        ).stream()
        
        participating = db.collection("tournaments").where(
            filter=firestore.FieldFilter("participant_ids", "array_contains", user_uid)
        ).stream()

        results = {}
        for doc in list(owned) + list(participating):
            if doc.id not in results:
                data = doc.to_dict()
                if data:
                    data["id"] = doc.id
                    # Formatting logic remains same
                    raw_date = data.get("start_date") or data.get("date")
                    if raw_date and hasattr(raw_date, "to_datetime"):
                        data["date_display"] = raw_date.to_datetime().strftime("%b %d, %Y")
                    results[doc.id] = data

        return list(results.values())

    @staticmethod
    def create_tournament(data: dict[str, Any], user_uid: str, db: Client | None = None) -> str:
        """Create a tournament with the enriched location_data from main."""
        if db is None:
            db = firestore.client()
        user_ref = db.collection("users").document(user_uid)

        tournament_payload = {
            "name": data["name"],
            "date": data["date"],
            "location": data["location"],
            "matchType": data.get("matchType") or data.get("mode", "SINGLES").lower(),
            "mode": data.get("mode", "SINGLES"),
            "location_data": data.get("location_data"), # From main branch
            "description": data.get("description"),
            "format": data.get("format", "ROUND_ROBIN"),
            "ownerRef": user_ref,
            "organizer_id": user_uid,
            "status": "Active",
            "participants": [{"userRef": user_ref, "status": "accepted"}],
            "participant_ids": [user_uid],
            "createdAt": firestore.SERVER_TIMESTAMP,
        }
        _, ref = db.collection("tournaments").add(tournament_payload)
        return str(ref.id)

    @staticmethod
    def update_tournament(tournament_id: str, user_uid: str, update_data: dict[str, Any], db: Client | None = None) -> None:
        """Update tournament with check for existing matches using FieldFilter."""
        if db is None:
            db = firestore.client()
        ref = db.collection("tournaments").document(tournament_id)
        # ... (Ownership check logic)

        if "matchType" in update_data:
            matches = db.collection("matches").where(
                filter=firestore.FieldFilter("tournamentId", "==", tournament_id)
            ).limit(1).stream()
            
            if any(matches):
                del update_data["matchType"]

        ref.update(update_data)

    # ... (remaining methods like invite_player, accept_invite, etc. follow the fix branch's FieldFilter pattern)