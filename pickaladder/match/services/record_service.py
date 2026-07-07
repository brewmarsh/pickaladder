from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, cast

from firebase_admin import firestore

from pickaladder.core.constants import GLOBAL_LEADERBOARD_MIN_GAMES

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client

    from pickaladder.user.models import User

logger = logging.getLogger(__name__)


class MatchRecordService:
    @staticmethod
    def calculate_rank_decay(user_data: dict[str, Any]) -> float:
        """Calculate ELO penalty based on inactivity."""
        last_match_date = user_data.get("last_match_date")
        if not last_match_date:
            # If no last match date, we can't calculate decay
            return 0.0

        # Handle different date formats (datetime or string)
        if isinstance(last_match_date, str):
            try:
                # Firestore often returns ISO strings
                dt = datetime.fromisoformat(last_match_date.replace("Z", "+00:00"))
            except ValueError:
                return 0.0
        elif isinstance(last_match_date, datetime):
            dt = last_match_date
        else:
            return 0.0

        # Ensure it's timezone aware
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        days_inactive = (datetime.now(timezone.utc) - dt).days

        # Define decay parameters
        DECAY_THRESHOLD_DAYS = 30
        DECAY_RATE_PER_DAY = 5.0  # Lose 5 ELO points per day after 30 days

        if days_inactive > DECAY_THRESHOLD_DAYS:
            penalty = (days_inactive - DECAY_THRESHOLD_DAYS) * DECAY_RATE_PER_DAY
            return float(penalty)

        return 0.0

    @staticmethod
    def get_player_record(
        db: Client,
        player_ref: Any,
    ) -> dict[str, int]:
        """Calculate win/loss record for a player by doc reference using denormalized stats."""
        if hasattr(player_ref, "get"):
            doc = player_ref.get()
        else:
            doc = db.collection("users").document(str(player_ref)).get()

        if doc.exists:
            data = doc.to_dict() or {}
            stats = data.get("stats", {})
            return {
                "wins": stats.get("wins", 0),
                "losses": stats.get("losses", 0),
            }

        return {"wins": 0, "losses": 0}

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
    def _get_rolling_window_start(days: int = 7) -> datetime:
        """Calculate the start of the rolling date window."""
        return datetime.now(timezone.utc) - timedelta(days=days)

    @staticmethod
    def _calculate_performance_metrics(
        db: Client,
        start_date: datetime,
    ) -> dict[str, int]:
        """Aggregate win counts for players since the given start date."""
        query = db.collection("matches").where(
            filter=firestore.FieldFilter("matchDate", ">=", start_date),
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
                    },
                )

        results.sort(key=lambda x: x["weekly_wins"], reverse=True)
        return results

    @staticmethod
    def get_leaderboard_data(
        db: Client,
        limit: int = 50,
        min_games: int = GLOBAL_LEADERBOARD_MIN_GAMES,
    ) -> list[User]:
        """Fetch data for the global leaderboard using denormalized stats."""
        players: list[User] = []
        # Optimization: Fetch users and use their denormalized stats
        # This avoids the O(U*M) bottleneck of streaming matches for every user
        for u_snap in db.collection("users").stream():
            user_data = cast("dict[str, Any]", u_snap.to_dict() or {})
            user_data["id"] = u_snap.id

            stats = user_data.get("stats", {})
            wins = stats.get("wins", 0)
            losses = stats.get("losses", 0)
            # Use elo, fallback to DUPR, then default to 1200.0
            elo = stats.get("elo")
            if elo is None:
                elo = (
                    user_data.get("duprRating")
                    or user_data.get("dupr_rating")
                    or 1200.0
                )

            # Apply rank decay penalty
            penalty = MatchRecordService.calculate_rank_decay(user_data)
            elo = max(100.0, float(elo) - penalty)
            user_data["is_inactive"] = penalty > 0

            games = wins + losses
            if games >= min_games:
                user_data.update(
                    {
                        "wins": wins,
                        "losses": losses,
                        "games_played": games,
                        "elo": float(elo),
                        "win_percentage": float((wins / games) * 100)
                        if games > 0
                        else 0.0,
                    },
                )
                players.append(cast("User", user_data))

        # Sort by ELO descending, then by win percentage as a tie-breaker
        players.sort(
            key=lambda p: (p.get("elo", 0.0), p.get("win_percentage", 0.0)),
            reverse=True,
        )
        return players[:limit]
