"""Tournament service for business logic."""

from __future__ import annotations

from typing import Any

from firebase_admin import firestore


class TournamentService:
    """Service class for tournament-related operations."""

    @staticmethod
    def list_tournaments(user_id: str, db: Any = None) -> list[dict[str, Any]]:
        """List all tournaments for a given user (owned or participating)."""
        if db is None:
            db = firestore.client()
        user_ref = db.collection("users").document(user_id)

        # Fetch tournaments where the user is an owner
        owned_tournaments = (
            db.collection("tournaments").where("ownerRef", "==", user_ref).stream()
        )

        # Fetch tournaments where user is a participant via the participant_ids array
        participating_tournaments = (
            db.collection("tournaments")
            .where("participant_ids", "array_contains", user_id)
            .stream()
        )

        tournaments = []
        seen_ids = set()

        for doc in owned_tournaments:
            data = doc.to_dict()
            if data:
                data["id"] = doc.id
                tournaments.append(data)
                seen_ids.add(doc.id)

        for doc in participating_tournaments:
            if doc.id not in seen_ids:
                data = doc.to_dict()
                if data:
                    data["id"] = doc.id
                    tournaments.append(data)
                    seen_ids.add(doc.id)

        return tournaments
