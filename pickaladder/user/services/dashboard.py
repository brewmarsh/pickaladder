"""Service for user dashboard data aggregation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pickaladder.user.services.activity import (
    get_active_tournaments,
    get_group_rankings,
    get_past_tournaments,
    get_pending_tournament_invites,
)
from pickaladder.user.services.core import get_user_by_id
from pickaladder.user.services.friendship import (
    get_user_friends,
    get_user_pending_requests,
)
from pickaladder.user.services.match_formatting import (
    format_matches_for_dashboard,
)
from pickaladder.user.services.match_stats import (
    _calculate_streak,
    get_recent_opponents,
    get_user_matches,
)

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client


def get_dashboard_data(db: Client, user_id: str) -> dict[str, Any]:
    """Aggregate all data required for the user dashboard."""
    from pickaladder.user.helpers import calculate_onboarding_progress

    # 1. Fetch user and vanity stats
    user_data, vanity_metrics = _fetch_vanity_stats(db, user_id)

    # 2. Fetch match activity
    match_data = _fetch_recent_activity(db, user_id)

    # 3. Fetch social and tournament data
    social_data = _fetch_social_and_tournaments(db, user_id)

    # 4. Calculate Onboarding Progress
    onboarding_progress = calculate_onboarding_progress(
        user_data,
        len(match_data["matches"]),
        len(social_data["group_rankings"]),
        len(social_data["friends"]),
    )

    # Assemble final stats object
    stats = {
        **vanity_metrics,
        "current_streak": match_data["current_streak"],
        "streak_type": match_data["streak_type"],
        "processed_matches": [
            {"doc": d, "data": d.to_dict()} for d in match_data["recent_docs"]
        ],
    }

    return {
        "user": user_data,
        "onboarding_progress": onboarding_progress,
        "matches": match_data["matches"],
        "next_cursor": match_data["next_cursor"],
        "stats": stats,
        "current_streak": match_data["current_streak"],
        "recent_opponents": match_data["recent_opponents"],
        **social_data,
    }


def _fetch_vanity_stats(
    db: Client, user_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Fetch user document and calculate vanity metrics."""
    from pickaladder.user.helpers import calculate_vanity_metrics

    user_data = get_user_by_id(db, user_id) or {}
    user_stats = user_data.get("stats")
    if not isinstance(user_stats, dict):
        user_stats = {}

    vanity_metrics = calculate_vanity_metrics(user_stats)
    return user_data, vanity_metrics


def _fetch_recent_activity(db: Client, user_id: str) -> dict[str, Any]:
    """Fetch recent matches and calculate engagement stats."""
    from pickaladder.user.helpers import extract_match_results_for_streak

    recent_docs = get_user_matches(db, user_id, limit=20)
    matches = format_matches_for_dashboard(db, recent_docs, user_id)
    next_cursor = recent_docs[-1].id if recent_docs else None

    processed = extract_match_results_for_streak(recent_docs, user_id)
    current_streak, streak_type = _calculate_streak(processed)
    recent_opponents = get_recent_opponents(db, user_id, recent_docs)

    return {
        "recent_docs": recent_docs,
        "matches": matches,
        "next_cursor": next_cursor,
        "current_streak": current_streak,
        "streak_type": streak_type,
        "recent_opponents": recent_opponents,
    }


def _fetch_social_and_tournaments(db: Client, user_id: str) -> dict[str, Any]:
    """Fetch social relations and tournament participation data."""
    return {
        "friends": get_user_friends(db, user_id),
        "requests": get_user_pending_requests(db, user_id),
        "group_rankings": get_group_rankings(db, user_id),
        "pending_tournament_invites": get_pending_tournament_invites(db, user_id),
        "active_tournaments": get_active_tournaments(db, user_id),
        "past_tournaments": get_past_tournaments(db, user_id),
    }
