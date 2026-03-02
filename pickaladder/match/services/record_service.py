from __future__ import annotations

import datetime
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
    def _get_rolling_window_start(days: int = 7) -> datetime.datetime:
        """Calculate the start of the rolling date window."""
        return datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            days=days
        )

    @staticmethod
    def _calculate_performance_metrics(
        db: Client, start_date: datetime.datetime
    ) -> dict[str, int]:
        """Aggregate win counts for players since the given start date."""
        query = db.collection("matches").where(
            filter=firestore.FieldFilter("matchDate", ">=", start_date)
        )
        win_counts: dict[str, int] = {}
        for snap in query.stream():
            data = snap.to_dict() or {}
            winners = data.get("winners") or []
            if wid := data.get("winnerId"):
                winners = [wid]
            for uid in winners:
                if isinstance(uid, str):
                    win_counts[uid] = win_counts.get(uid, 0) + 1
        return win_counts

    @staticmethod
    def get_rising_stars(db: Client, limit: int = 3) -> list[dict[str, Any]]:
        """Identify players with the most wins in the last 7 days."""
        start_date = MatchRecordService._get_rolling_window_start(7)
        win_counts = MatchRecordService._calculate_performance_metrics(db, start_date)

        if not win_counts:
            return []

        sorted_uids = sorted(win_counts.items(), key=lambda x: x[1], reverse=True)[
            :limit
        ]
        top_uids = [u for u, _ in sorted_uids]
        top_counts = dict(sorted_uids)

        u_refs = [db.collection("users").document(uid) for uid in top_uids]
        results = []
        for u_snap in db.get_all(u_refs):
            if u_snap.exists:
                u_data = u_snap.to_dict() or {}
                uid = u_snap.id
                results.append(
                    {
                        "id": uid,
                        "name": u_data.get("name") or u_data.get("username", "Unknown"),
                        "username": u_data.get("username", "Unknown"),
                        "profilePictureUrl": u_data.get("profilePictureUrl"),
                        "weekly_wins": top_counts.get(uid, 0),
                    }
                )

        results.sort(key=lambda x: x["weekly_wins"], reverse=True)
        return results

    @staticmethod
    def get_leaderboard_data(
        db: Client, limit: int = 50, min_games: int = GLOBAL_LEADERBOARD_MIN_GAMES
    ) -> list[User]:
        """Fetch data for the global leaderboard using cached statistics."""
        players: list[User] = []
        for u_snap in db.collection("users").stream():
            user_data = cast(dict[str, Any], u_snap.to_dict() or {})
            user_data["id"] = u_snap.id

            stats = cast(dict[str, Any], user_data.get("stats") or {})
            wins = int(stats.get("wins", 0))
            losses = int(stats.get("losses", 0))
            games = wins + losses

            if games >= min_games:
                user_data.update(
                    {
                        "wins": wins,
                        "losses": losses,
                        "games_played": games,
                        "win_percentage": float((wins / games) * 100)
                        if games > 0
                        else 0.0,
                    }
                )
                players.append(cast("User", user_data))

        players.sort(
            key=lambda p: (p.get("win_percentage", 0), p.get("wins", 0)), reverse=True
        )
        return players[:limit]
