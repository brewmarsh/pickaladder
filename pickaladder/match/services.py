"""Service for match-related business logic."""

from __future__ import annotations

import datetime
from typing import Any

from firebase_admin import firestore

from pickaladder.teams.utils import get_or_create_team

UPSET_THRESHOLD = 0.25


class MatchService:
    """Match service for business logic."""

    @staticmethod
    def create_match_record(
        db: Any,
        form_data: Any,
        user_id: str,
        group_id: str | None = None,
        tournament_id: str | None = None,
    ) -> str:
        """Centralize match recording business logic.

        This includes converting form IDs to References, determining the winner,
        detecting upsets, updating streaks, and batching Firestore operations.
        """
        batch = db.batch()

        # 1. Helper to extract data from form or dict
        def get_data(key: str) -> Any:
            if isinstance(form_data, dict):
                return form_data.get(key)
            return getattr(form_data, key).data

        match_type = get_data("match_type")
        player1_id = get_data("player1") or user_id
        player2_id = get_data("player2")
        player1_score = int(get_data("player1_score"))
        player2_score = int(get_data("player2_score"))
        group_id = group_id or get_data("group_id")
        tournament_id = tournament_id or get_data("tournament_id")

        # 2. Date handling
        match_date_input = get_data("match_date")
        if isinstance(match_date_input, str) and match_date_input:
            match_date = datetime.datetime.strptime(match_date_input, "%Y-%m-%d")
        elif isinstance(match_date_input, datetime.date):
            match_date = datetime.datetime.combine(match_date_input, datetime.time.min)
        elif isinstance(match_date_input, datetime.datetime):
            match_date = match_date_input
        else:
            match_date = datetime.datetime.now()

        # 3. Fetch player data for ratings and streaks
        player_ids = [player1_id, player2_id]
        if match_type == "doubles":
            partner_id = get_data("partner")
            opponent2_id = get_data("opponent2")
            player_ids.extend([partner_id, opponent2_id])

        player_refs = [db.collection("users").document(pid) for pid in player_ids]
        player_docs = db.get_all(player_refs)
        players_map = {doc.id: doc.to_dict() or {} for doc in player_docs if doc.exists}

        # 4. Construct Match Data
        match_data = {
            "player1Score": player1_score,
            "player2Score": player2_score,
            "matchDate": match_date,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "matchType": match_type,
            "recordedBy": user_id,
        }
        if group_id:
            match_data["groupId"] = group_id
        if tournament_id:
            match_data["tournamentId"] = tournament_id

        # 5. Winner determination and Upset detection
        winner_slot = "player1" if player1_score > player2_score else "player2"
        match_data["winner"] = (
            "team1"
            if (match_type == "doubles" and winner_slot == "player1")
            else "team2"
            if (match_type == "doubles" and winner_slot == "player2")
            else winner_slot
        )

        is_upset = False
        if match_type == "singles":
            match_data["player1Ref"] = db.collection("users").document(player1_id)
            match_data["player2Ref"] = db.collection("users").document(player2_id)

            p1_rating = float(players_map.get(player1_id, {}).get("dupr_rating") or 0.0)
            p2_rating = float(players_map.get(player2_id, {}).get("dupr_rating") or 0.0)

            if winner_slot == "player1" and (p2_rating - p1_rating) >= UPSET_THRESHOLD:
                is_upset = True
            elif (
                winner_slot == "player2" and (p1_rating - p2_rating) >= UPSET_THRESHOLD
            ):
                is_upset = True

        elif match_type == "doubles":
            t1_p1_id, t1_p2_id = player1_id, get_data("partner")
            t2_p1_id, t2_p2_id = player2_id, get_data("opponent2")

            team1_id = get_or_create_team(t1_p1_id, t1_p2_id)
            team2_id = get_or_create_team(t2_p1_id, t2_p2_id)

            match_data["team1Id"] = team1_id
            match_data["team2Id"] = team2_id
            match_data["team1"] = [
                db.collection("users").document(t1_p1_id),
                db.collection("users").document(t1_p2_id),
            ]
            match_data["team2"] = [
                db.collection("users").document(t2_p1_id),
                db.collection("users").document(t2_p2_id),
            ]
            match_data["team1Ref"] = db.collection("teams").document(team1_id)
            match_data["team2Ref"] = db.collection("teams").document(team2_id)

            # Update team stats
            if winner_slot == "player1":
                batch.update(
                    match_data["team1Ref"], {"stats.wins": firestore.Increment(1)}
                )
                batch.update(
                    match_data["team2Ref"], {"stats.losses": firestore.Increment(1)}
                )
            else:
                batch.update(
                    match_data["team1Ref"], {"stats.losses": firestore.Increment(1)}
                )
                batch.update(
                    match_data["team2Ref"], {"stats.wins": firestore.Increment(1)}
                )

            # Upset detection for doubles (average rating)
            t1_rating = (
                float(players_map.get(t1_p1_id, {}).get("dupr_rating") or 0.0)
                + float(players_map.get(t1_p2_id, {}).get("dupr_rating") or 0.0)
            ) / 2
            t2_rating = (
                float(players_map.get(t2_p1_id, {}).get("dupr_rating") or 0.0)
                + float(players_map.get(t2_p2_id, {}).get("dupr_rating") or 0.0)
            ) / 2

            if winner_slot == "player1" and (t2_rating - t1_rating) >= UPSET_THRESHOLD:
                is_upset = True
            elif (
                winner_slot == "player2" and (t1_rating - t2_rating) >= UPSET_THRESHOLD
            ):
                is_upset = True

        match_data["is_upset"] = is_upset

        # 6. Update individual player stats and streaks
        for pid in player_ids:
            p_ref = db.collection("users").document(pid)
            p_data = players_map.get(pid, {})

            # Determine if this player won
            if match_type == "singles":
                won = (pid == player1_id and winner_slot == "player1") or (
                    pid == player2_id and winner_slot == "player2"
                )
            elif pid in [player1_id, get_data("partner")]:
                won = winner_slot == "player1"
            else:
                won = winner_slot == "player2"

            # Stats update
            stats = p_data.get("stats", {})
            current_wins = stats.get("wins", 0)
            current_losses = stats.get("losses", 0)
            current_streak = stats.get("current_streak", 0)
            streak_type = stats.get("streak_type", "W")

            if won:
                new_wins = current_wins + 1
                new_losses = current_losses
                if streak_type == "W":
                    new_streak = current_streak + 1
                else:
                    new_streak = 1
                new_streak_type = "W"
            else:
                new_wins = current_wins
                new_losses = current_losses + 1
                if streak_type == "L":
                    new_streak = current_streak + 1
                else:
                    new_streak = 1
                new_streak_type = "L"

            update_fields = {
                "stats": {
                    "wins": new_wins,
                    "losses": new_losses,
                    "current_streak": new_streak,
                    "streak_type": new_streak_type,
                },
                "lastMatchRecordedType": match_type,
            }
            batch.set(p_ref, update_fields, merge=True)

        # 7. Add match and commit
        match_ref = db.collection("matches").document()
        batch.set(match_ref, match_data)
        batch.commit()

        return match_ref.id
