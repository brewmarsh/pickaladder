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
    def get_rising_stars(db: Client, limit: int = 3) -> list[dict[str, Any]]:
        """Fetch users with the most wins in the last 7 days."""
        from datetime import datetime, timedelta, timezone

        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        matches_query = db.collection("matches").where(
            filter=firestore.FieldFilter("createdAt", ">=", seven_days_ago)
        )

        win_counts: dict[str, int] = {}
        for m_snap in matches_query.stream():
            m_data = m_snap.to_dict() or {}
            winners = m_data.get("winners") or []
            for uid in winners:
                win_counts[uid] = win_counts.get(uid, 0) + 1

        if not win_counts:
            return []

        # Sort and take top IDs
        top_uids_with_counts = sorted(
            win_counts.items(), key=lambda x: x[1], reverse=True
        )[:limit]
        top_win_map = dict(top_uids_with_counts)
        top_uids = list(top_win_map.keys())

        # Bulk fetch user data
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
                        "username": u_data.get("username"),
                        "profilePictureUrl": u_data.get("profilePictureUrl"),
                        "weekly_wins": top_win_map.get(uid, 0),
                    }
                )

        # Ensure order is maintained after bulk fetch
        results.sort(key=lambda x: x["weekly_wins"], reverse=True)
        return results

    @staticmethod
    def get_leaderboard_data(
        db: Client, limit: int = 50, min_games: int = GLOBAL_LEADERBOARD_MIN_GAMES
    ) -> list[User]:
        """Fetch data for the global leaderboard using cached statistics."""
        players: list[User] = []
        for u_snap in db.collection("users").stream():
            # Cast to dict for flexible access to 'stats' map
            user_data = cast(dict[str, Any], u_snap.to_dict() or {})
            user_data["id"] = u_snap.id

            # Use cached stats from the user document instead of querying matches
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
