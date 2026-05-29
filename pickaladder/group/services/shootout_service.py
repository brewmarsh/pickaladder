"""Service for automated court movement (Shootout) logic."""

from __future__ import annotations


class ShootoutService:
    """Service for automated court movement (Shootout) logic."""

    @staticmethod
    def calculate_next_assignments(
        player_results: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        """
        Calculate next court assignments based on current match results.

        player_results should be a list of dicts:
        {
            "uid": str,
            "court": int, (1-indexed, 1 is top court)
            "won": bool
        }

        Returns a list of dicts with "uid" and "next_court".
        """
        if not player_results:
            return []

        # Group by court
        courts: dict[int, list[dict[str, object]]] = {}
        for res in player_results:
            c = res["court"]
            if c not in courts:
                courts[c] = []
            courts[c].append(res)

        sorted_court_ids = sorted(courts.keys())
        assignments = []

        for court_id in sorted_court_ids:
            court_players = courts[court_id]

            for player in court_players:
                uid = player["uid"]
                won = player["won"]
                next_court = court_id

                if won:
                    # Winners move up (decrement court_id)
                    if court_id > 1:
                        next_court = court_id - 1
                # Losers move down (increment court_id)
                elif court_id < max(sorted_court_ids):
                    next_court = court_id + 1

                assignments.append({"uid": uid, "next_court": next_court})

        return assignments

    @staticmethod
    def group_players_to_courts(
        player_uids: list[str], players_per_court: int = 4
    ) -> list[dict[str, object]]:
        """
        Initially group players into courts based on current ranking.
        Assumes player_uids are already sorted by rank (ELO).
        """
        assignments = []
        for i, uid in enumerate(player_uids):
            court_id = (i // players_per_court) + 1
            assignments.append({"uid": uid, "court": court_id})
        return assignments
