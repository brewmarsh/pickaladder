from __future__ import annotations

from typing import TYPE_CHECKING, Any

from google.cloud import firestore

from pickaladder.user.services import UserService

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client


class PredictionService:
    """Service for match predictions."""

    @staticmethod
    def predict_matchup(
        db: Client, team1_ids: list[str], team2_ids: list[str]
    ) -> dict[str, Any]:
        """Predict the outcome of a matchup between two teams."""
        # 1. H2H (50% weight)
        h2h_win_rate = PredictionService._get_h2h_win_rate(db, team1_ids, team2_ids)

        # 2. Form (30% weight)
        team1_form = PredictionService._get_team_form(db, team1_ids)
        team2_form = PredictionService._get_team_form(db, team2_ids)

        # 3. Global (20% weight)
        team1_global = PredictionService._get_team_global(db, team1_ids)
        team2_global = PredictionService._get_team_global(db, team2_ids)

        # 4. Weighted Score
        # Convert win rates to differentials (-100 to 100)
        h2h_diff = (h2h_win_rate - 50) * 2
        form_diff = team1_form - team2_form
        global_diff = team1_global - team2_global

        score_diff = (h2h_diff * 0.5) + (form_diff * 0.3) + (global_diff * 0.2)

        # Normalize to 0-100 probability for Team 1
        team1_prob = 50 + (score_diff / 2)
        team1_prob = max(0, min(100, team1_prob))
        team2_prob = 100 - team1_prob

        # Insight Generation
        hot_streak_threshold = 80
        dominance_threshold = 75
        weak_dominance_threshold = 25

        if team1_form > hot_streak_threshold or team2_form > hot_streak_threshold:
            insight = "Team is on a hot streak!"
        elif (
            h2h_win_rate > dominance_threshold
            or h2h_win_rate < weak_dominance_threshold
        ):
            insight = "Historical dominance."
        else:
            insight = "A closely matched game."

        return {
            "team1_prob": round(team1_prob),
            "team2_prob": round(team2_prob),
            "insight": insight,
        }

    @staticmethod
    def _get_h2h_win_rate(
        db: Client, team1_ids: list[str], team2_ids: list[str]
    ) -> float:
        """Calculate the head-to-head win rate for Team 1 against Team 2."""
        if len(team1_ids) == 1 and len(team2_ids) == 1:
            # Singles H2H
            stats = UserService.get_h2h_stats(db, team1_ids[0], team2_ids[0])
            if not stats:
                return 50.0
            total = stats["wins"] + stats["losses"]
            if total == 0:
                return 50.0
            return (stats["wins"] / total) * 100
        else:
            # Doubles H2H - basic implementation
            # We look for matches where team1_ids and team2_ids played each other
            matches_ref = db.collection("matches")
            query = matches_ref.where(
                filter=firestore.FieldFilter("matchType", "==", "doubles")
            ).where(filter=firestore.FieldFilter("status", "==", "completed"))

            # Filtering in memory for complex team combinations
            wins = 0
            total = 0
            t1_set = set(team1_ids)
            t2_set = set(team2_ids)

            for match in query.stream():
                data = match.to_dict()
                if not data:
                    continue
                m_t1 = set(data.get("team1Id", []))
                m_t2 = set(data.get("team2Id", []))

                if m_t1 == t1_set and m_t2 == t2_set:
                    total += 1
                    if data.get("winnerId") == "team1":
                        wins += 1
                elif m_t1 == t2_set and m_t2 == t1_set:
                    total += 1
                    if data.get("winnerId") == "team2":
                        wins += 1

            if total == 0:
                return 50.0
            return (wins / total) * 100

    @staticmethod
    def _get_team_form(db: Client, player_ids: list[str]) -> float:
        """Calculate the average form (last 5 games) for a team."""
        if not player_ids:
            return 50.0
        forms = []
        for pid in player_ids:
            matches = UserService.get_user_matches(db, pid)
            stats = UserService.calculate_stats(matches, pid)
            recent_matches = stats["processed_matches"][:5]
            if not recent_matches:
                forms.append(50.0)
            else:
                wins = sum(1 for m in recent_matches if m["user_won"])
                forms.append((wins / len(recent_matches)) * 100)
        return sum(forms) / len(forms)

    @staticmethod
    def _get_team_global(db: Client, player_ids: list[str]) -> float:
        """Calculate the average global win rate for a team."""
        if not player_ids:
            return 50.0
        rates = []
        for pid in player_ids:
            matches = UserService.get_user_matches(db, pid)
            stats = UserService.calculate_stats(matches, pid)
            if stats["total_games"] == 0:
                rates.append(50.0)
            else:
                rates.append(stats["win_rate"])
        return sum(rates) / len(rates)
