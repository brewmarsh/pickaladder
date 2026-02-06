"""Statistics and ranking logic for users."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any

from firebase_admin import firestore

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client


class UserStats:
    """Service for calculating user statistics and rankings.

    This class handles the 'math' of win rates, streaks, head-to-head records,
    and group leaderboards.
    """

    @staticmethod
    def _get_user_match_won_lost(
        match_data: dict[str, Any], user_id: str
    ) -> tuple[bool, bool]:
        """Determine if the user won or lost the match, including handling of draws."""
        match_type = match_data.get("matchType", "singles")
        p1_score = match_data.get("player1Score", 0)
        p2_score = match_data.get("player2Score", 0)

        user_won = False
        user_lost = False

        if match_type == "doubles":
            team1_refs = match_data.get("team1", [])
            in_team1 = any(ref.id == user_id for ref in team1_refs)
            if in_team1:
                user_won, user_lost = (p1_score > p2_score), (p1_score <= p2_score)
            else:
                user_won, user_lost = (p2_score > p1_score), (p2_score <= p1_score)
        else:
            p1_ref = match_data.get("player1Ref")
            is_player1 = p1_ref and p1_ref.id == user_id
            if is_player1:
                user_won, user_lost = (p1_score > p2_score), (p1_score <= p2_score)
            else:
                user_won, user_lost = (p2_score > p1_score), (p2_score <= p1_score)

        return user_won, user_lost

    @staticmethod
    def _calculate_streak(processed: list[dict[str, Any]]) -> tuple[int, str]:
        """Calculate current streak from processed matches."""
        if not processed:
            return 0, "N/A"

        last_won = processed[0]["user_won"]
        streak_type = "W" if last_won else "L"
        current_streak = 0
        for m in processed:
            if m["user_won"] == last_won:
                current_streak += 1
            else:
                break
        return current_streak, streak_type

    @staticmethod
    def calculate(matches: list[DocumentSnapshot], user_id: str) -> dict[str, Any]:
        """Calculate aggregate performance statistics from a list of matches."""
        wins = losses = 0
        processed = []

        for match_doc in matches:
            match_data = match_doc.to_dict()
            if not match_data:
                continue

            won, lost = UserStats._get_user_match_won_lost(match_data, user_id)
            if won:
                wins += 1
            elif lost:
                losses += 1

            processed.append(
                {
                    "doc": match_doc,
                    "data": match_data,
                    "date": match_data.get("matchDate") or match_doc.create_time,
                    "user_won": won,
                }
            )

        total = wins + losses
        win_rate = (wins / total) * 100 if total > 0 else 0
        processed.sort(key=lambda x: x["date"] or datetime.datetime.min, reverse=True)

        streak, s_type = UserStats._calculate_streak(processed)

        return {
            "wins": wins,
            "losses": losses,
            "total_games": total,
            "win_rate": win_rate,
            "current_streak": streak,
            "streak_type": s_type,
            "processed_matches": processed,
        }

    @staticmethod
    def _process_h2h_match(
        data: dict[str, Any], user_id_1: str, user_id_2: str
    ) -> tuple[int, int, int]:
        """Process a single match for H2H stats and return (wins, losses, points)."""
        wins = losses = points = 0
        match_type = data.get("matchType", "singles")

        if match_type == "singles":
            is_p1 = data.get("player1Id") == user_id_1
            winner_id = data.get("winnerId")
            if winner_id == user_id_1:
                wins += 1
            elif winner_id == user_id_2:
                losses += 1

            p1_score = data.get("player1Score", 0)
            p2_score = data.get("player2Score", 0)
            points += (p1_score - p2_score) if is_p1 else (p2_score - p1_score)
        else:
            team1_ids = data.get("team1Id", [])
            team2_ids = data.get("team2Id", [])
            winner_id = data.get("winnerId")

            if user_id_1 in team1_ids and user_id_2 in team2_ids:
                if winner_id == "team1":
                    wins += 1
                else:
                    losses += 1
                points += data.get("player1Score", 0) - data.get("player2Score", 0)
            elif user_id_1 in team2_ids and user_id_2 in team1_ids:
                if winner_id == "team2":
                    wins += 1
                else:
                    losses += 1
                points += data.get("player2Score", 0) - data.get("player1Score", 0)

        return wins, losses, points

    @staticmethod
    def get_h2h_stats(
        db: Client, user_id_1: str, user_id_2: str
    ) -> dict[str, Any] | None:
        """Fetch head-to-head statistics between two users."""
        wins = losses = points = 0

        # Build queries
        matches_ref = db.collection("matches")
        common_filters = [firestore.FieldFilter("status", "==", "completed")]

        q1 = matches_ref.where(
            filter=firestore.FieldFilter("player1Id", "==", user_id_1)
        ).where(filter=firestore.FieldFilter("player2Id", "==", user_id_2))
        q2 = matches_ref.where(
            filter=firestore.FieldFilter("player1Id", "==", user_id_2)
        ).where(filter=firestore.FieldFilter("player2Id", "==", user_id_1))
        q3 = matches_ref.where(
            filter=firestore.FieldFilter("participants", "array_contains", user_id_1)
        ).where(filter=firestore.FieldFilter("matchType", "==", "doubles"))

        for q_obj in [q1, q2, q3]:
            final_q = q_obj
            for f in common_filters:
                final_q = final_q.where(filter=f)

            for match in final_q.stream():
                data = match.to_dict()
                if data:
                    w, l_count, p_diff = UserStats._process_h2h_match(
                        data, user_id_1, user_id_2
                    )
                    wins += w
                    losses += l_count
                    points += p_diff

        if wins > 0 or losses > 0:
            return {"wins": wins, "losses": losses, "point_diff": points}
        return None

    @staticmethod
    def get_group_rankings(db: Client, user_id: str) -> list[dict[str, Any]]:
        """Fetch group rankings for a user."""
        from pickaladder.group.utils import get_group_leaderboard  # noqa: PLC0415

        user_ref = db.collection("users").document(user_id)
        group_rankings = []
        my_groups_query = (
            db.collection("groups")
            .where(filter=firestore.FieldFilter("members", "array_contains", user_ref))
            .stream()
        )
        for group_doc in my_groups_query:
            group_data = group_doc.to_dict()
            if group_data is None:
                continue
            leaderboard = get_group_leaderboard(group_doc.id)
            user_ranking_data = None
            for i, player in enumerate(leaderboard):
                if player["id"] == user_id:
                    rank = i + 1
                    user_ranking_data = {
                        "group_id": group_doc.id,
                        "group_name": group_data.get("name", "N/A"),
                        "rank": rank,
                        "points": player.get("avg_score", 0),
                        "form": player.get("form", []),
                    }
                    if i > 0:
                        player_above = leaderboard[i - 1]
                        user_ranking_data["player_above"] = player_above.get("name")
                        user_ranking_data["points_to_overtake"] = player_above.get(
                            "avg_score", 0
                        ) - player.get("avg_score", 0)
                    break

            if user_ranking_data:
                group_rankings.append(user_ranking_data)
            else:
                group_rankings.append(
                    {
                        "group_id": group_doc.id,
                        "group_name": group_data.get("name", "N/A"),
                        "rank": "N/A",
                        "points": 0,
                        "form": [],
                    }
                )
        return group_rankings
