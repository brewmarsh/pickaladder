from __future__ import annotations

from typing import Any

MIN_PARTICIPANTS = 2


class TournamentGenerator:
    """Utility class to generate tournament match pairings."""

    @staticmethod
    def _get_RR_pair_ids(
        ids: list[str],
    ) -> list[tuple[str | None, str | None]]:
        """Compute Round Robin pairing IDs using the Circle Method (Pure Math)."""
        temp_ids: list[str | None] = list(ids)
        if len(temp_ids) % 2 != 0:
            temp_ids.append(None)
        n, pairs = len(temp_ids), []
        for _ in range(n - 1):
            for i in range(n // 2):
                pairs.append((temp_ids[i], temp_ids[n - 1 - i]))
            temp_ids = [temp_ids[0]] + [temp_ids[-1]] + temp_ids[1:-1]
        return pairs

    @staticmethod
    def generate_round_robin(participant_ids: list[str]) -> list[dict[str, Any]]:
        """Generate Round Robin pairings."""
        from firebase_admin import firestore

        if not participant_ids or len(participant_ids) < MIN_PARTICIPANTS:
            return []
        db, pairings = firestore.client(), []
        for p1, p2 in TournamentGenerator._get_RR_pair_ids(list(participant_ids)):
            if p1 and p2:
                pairings.append(
                    {
                        "player1Ref": db.collection("users").document(p1),
                        "player2Ref": db.collection("users").document(p2),
                        "matchType": "singles",
                        "status": "DRAFT",
                        "createdAt": firestore.SERVER_TIMESTAMP,
                        "participants": [p1, p2],
                    }
                )
        return pairings
