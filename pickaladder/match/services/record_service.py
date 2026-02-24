from __future__ import annotations
from typing import TYPE_CHECKING, Any, cast
from firebase_admin import firestore
from pickaladder.core.constants import GLOBAL_LEADERBOARD_MIN_GAMES

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client
    from pickaladder.user.models import User

class MatchRecordService:
    @staticmethod
    def get_player_record(db: Client, player_ref: Any) -> dict[str, int]:
        """Calculate win/loss record for a player by doc reference."""
        wins, losses = 0, 0
        uid = (
            player_ref.id
            if player_ref is not None and hasattr(player_ref, "id")
            else str(player_ref)
        )

        query = db.collection("matches").where(
            filter=firestore.FieldFilter("participants", "array_contains", uid)
        )

        for match in query.stream():
            data = match.to_dict()
            if not data:
                continue

            s1, s2 = data.get("player1Score", 0), data.get("player2Score", 0)
            if s1 == s2:
                continue

            is_team1 = MatchRecordService._is_user_on_team1(data, uid)
            if (is_team1 and s1 > s2) or (not is_team1 and s2 > s1):
                wins += 1
            else:
                losses += 1

        return {"wins": wins, "losses": losses}

    @staticmethod
    def _is_user_on_team1(data: dict[str, Any], uid: str) -> bool:
        """Determine if a user is on the Team 1 side of a match."""
        if data.get("matchType") == "doubles":
            team1_refs = data.get("team1", [])
            return any(
                (r.id if r is not None and hasattr(r, "id") else "") == uid
                for r in team1_refs
            )
        p1_ref = data.get("player1Ref")
        return (
            p1_ref.id if p1_ref is not None and hasattr(p1_ref, "id") else ""
        ) == uid

    @staticmethod
    def get_leaderboard_data(
        db: Client, limit: int = 50, min_games: int = GLOBAL_LEADERBOARD_MIN_GAMES
    ) -> list[User]:
        """Fetch data for the global leaderboard."""
        players: list[User] = []
        for u_snap in db.collection("users").stream():
            user_data = cast("User", u_snap.to_dict() or {})
            user_data["id"] = u_snap.id
            record = MatchRecordService.get_player_record(
                db, db.collection("users").document(u_snap.id)
            )

            games = record["wins"] + record["losses"]
            if games >= min_games:
                user_data.update(
                    {
                        "wins": record["wins"],
                        "losses": record["losses"],
                        "games_played": games,
                        "win_percentage": float((record["wins"] / games) * 100)
                        if games > 0
                        else 0.0,
                    }
                )
                players.append(user_data)

        players.sort(
            key=lambda p: (p.get("win_percentage", 0), p.get("wins", 0)), reverse=True
        )
        return players[:limit]
