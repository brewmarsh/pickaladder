from __future__ import annotations

import math
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
            temp_ids = [temp_ids[0], temp_ids[-1], *temp_ids[1:-1]]
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
                    },
                )
        return pairings

    @staticmethod
    def generate_pool_play(
        participant_ids: list[str],
        pool_count: int,
    ) -> list[dict[str, Any]]:
        """Divide participants into pools and generate Round Robin matches for each."""
        import random

        if not participant_ids or pool_count < 1:
            return []

        # Shuffle to ensure random distribution
        shuffled_ids = list(participant_ids)
        random.shuffle(shuffled_ids)

        # Split into pools
        pools: list[list[str]] = [[] for _ in range(pool_count)]
        for i, uid in enumerate(shuffled_ids):
            pools[i % pool_count].append(uid)

        all_pairings = []
        pool_labels = [chr(65 + i) for i in range(pool_count)]  # A, B, C...

        for i, pool_participants in enumerate(pools):
            if len(pool_participants) < MIN_PARTICIPANTS:
                continue

            pool_id = pool_labels[i]
            pool_pairings = TournamentGenerator.generate_round_robin(pool_participants)

            # Tag matches with pool_id
            for match in pool_pairings:
                match["pool_id"] = pool_id
                all_pairings.append(match)

        return all_pairings

    @staticmethod
    def _next_power_of_2(n: int) -> int:
        """Calculate the next power of 2 greater than or equal to n."""
        if n <= 0:
            return 1
        return 2 ** math.ceil(math.log2(n))

    @staticmethod
    def generate_single_elimination(
        seeded_ids: list[str],
    ) -> list[dict[str, Any]]:
        """Generate all rounds for a Single Elimination bracket.
        seeded_ids: List of participant UIDs sorted by seed (strongest first).
        """
        from firebase_admin import firestore

        db = firestore.client()

        n = len(seeded_ids)
        if n < MIN_PARTICIPANTS:
            return []

        bracket_size = TournamentGenerator._next_power_of_2(n)
        pairings = []

        # Round 1 (Initial pairings)
        full_roster: list[str | None] = list(seeded_ids) + [None] * (bracket_size - n)
        for i in range(bracket_size // 2):
            p1 = full_roster[i]
            p2 = full_roster[bracket_size - 1 - i]
            match_data = {
                "player1Ref": db.collection("users").document(p1) if p1 else None,
                "player2Ref": db.collection("users").document(p2) if p2 else None,
                "matchType": "singles",
                "round": 1,
                "bracketPosition": i,
                "bracketType": "WINNERS",
                "createdAt": firestore.SERVER_TIMESTAMP,
                "participants": [uid for uid in [p1, p2] if uid],
            }
            if p1 and not p2:
                match_data["status"] = "COMPLETED"
                match_data["winner"] = "team1"
                match_data["isBye"] = True
            else:
                match_data["status"] = "DRAFT"
            pairings.append(match_data)

        # Pre-create subsequent rounds (placeholder matches)
        # Winners move from P in round R to P//2 in round R+1
        num_rounds = int(math.log2(bracket_size))
        for r in range(2, num_rounds + 1):
            num_matches = bracket_size // (2**r)
            for i in range(num_matches):
                pairings.append(
                    {
                        "player1Ref": None,
                        "player2Ref": None,
                        "matchType": "singles",
                        "status": "WAITING",
                        "round": r,
                        "bracketPosition": i,
                        "bracketType": "WINNERS",
                        "createdAt": firestore.SERVER_TIMESTAMP,
                        "participants": [],
                    },
                )

        return pairings

    @staticmethod
    def generate_double_elimination(
        seeded_ids: list[str],
    ) -> list[dict[str, Any]]:
        """Generate all rounds for a Double Elimination bracket."""
        from firebase_admin import firestore

        # 1. Winners Bracket (Full structure)
        pairings = TournamentGenerator.generate_single_elimination(seeded_ids)

        n = len(seeded_ids)
        bracket_size = TournamentGenerator._next_power_of_2(n)
        num_winners_rounds = int(math.log2(bracket_size))

        # 2. Losers Bracket structure
        for r in range(1, (2 * num_winners_rounds) - 1):
            num_matches = bracket_size // (2 ** (math.ceil((r + 1) / 2) + 1))
            num_matches = max(num_matches, 1)  # Semi-final of losers

            for i in range(num_matches):
                pairings.append(
                    {
                        "player1Ref": None,
                        "player2Ref": None,
                        "matchType": "singles",
                        "status": "WAITING",
                        "round": r,
                        "bracketPosition": i,
                        "bracketType": "LOSERS",
                        "createdAt": firestore.SERVER_TIMESTAMP,
                        "participants": [],
                    },
                )

        # 3. Grand Finals
        pairings.append(
            {
                "player1Ref": None,
                "player2Ref": None,
                "matchType": "singles",
                "status": "WAITING",
                "round": num_winners_rounds + 1,
                "bracketPosition": 0,
                "bracketType": "FINALS",
                "isGrandFinal": True,
                "createdAt": firestore.SERVER_TIMESTAMP,
                "participants": [],
            },
        )

        return pairings
