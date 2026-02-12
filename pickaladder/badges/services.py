"""Service for badge evaluation and awarding."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from firebase_admin import firestore

from pickaladder.user.services.match_stats import calculate_stats, get_user_matches

from .models import BADGES

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client


HOT_STREAK_THRESHOLD = 3
CENTURY_CLUB_THRESHOLD = 100


class BadgeService:
    """Service class for badge-related operations."""

    @staticmethod
    def award_badge(db: Client, user_id: str, badge_id: str) -> bool:
        """Award a badge to a user if they don't already have it."""
        if badge_id not in BADGES:
            return False

        user_ref = db.collection("users").document(user_id)
        user_doc = cast("DocumentSnapshot", user_ref.get())
        if not user_doc.exists:
            return False

        user_data = user_doc.to_dict() or {}
        existing_badges = user_data.get("badges", [])

        # Check if user already has this badge
        if any(b.get("badge_id") == badge_id for b in existing_badges):
            return False

        # Atomic update to push to badges array
        badge_entry = {
            "badge_id": badge_id,
            "awarded_at": firestore.SERVER_TIMESTAMP,
        }
        user_ref.update({"badges": firestore.ArrayUnion([badge_entry])})
        return True

    @staticmethod
    def evaluate_post_match(db: Client, user_id: str) -> list[str]:
        """Evaluate and award badges based on user stats after a match."""
        matches = get_user_matches(db, user_id)
        stats = calculate_stats(matches, user_id)

        awarded_badge_ids = []

        # Logic: Rookie (1st match)
        if stats.get("total_games") == 1:
            if BadgeService.award_badge(db, user_id, "ROOKIE"):
                awarded_badge_ids.append("ROOKIE")

        # Logic: Century Club (100 matches)
        if stats.get("total_games") == CENTURY_CLUB_THRESHOLD:
            if BadgeService.award_badge(db, user_id, "CENTURY"):
                awarded_badge_ids.append("CENTURY")

        # Logic: On Fire (3 wins in a row)
        if (
            stats.get("current_streak") == HOT_STREAK_THRESHOLD
            and stats.get("streak_type") == "W"
        ):
            if BadgeService.award_badge(db, user_id, "HOT_STREAK"):
                awarded_badge_ids.append("HOT_STREAK")

        return awarded_badge_ids
