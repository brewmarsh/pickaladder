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
from pickaladder.user.services.match_stats import (
    calculate_stats,
    format_matches_for_dashboard,
    get_user_matches,
)

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client


def get_dashboard_data(db: Client, user_id: str) -> dict[str, Any]:
    """Aggregate all data required for the user dashboard."""
    # Fetch user matches and stats
    matches_all = get_user_matches(db, user_id)
    stats = calculate_stats(matches_all, user_id)

    # Prepare formatted matches (limit to 20 for dashboard)
    # calculate_stats already sorts them by date descending
    recent_matches_docs = [m["doc"] for m in stats["processed_matches"][:20]]
    matches = format_matches_for_dashboard(db, recent_matches_docs, user_id)

    # Fetch other related data
    friends = get_user_friends(db, user_id)
    requests_data = get_user_pending_requests(db, user_id)
    group_rankings = get_group_rankings(db, user_id)
    pending_tournament_invites = get_pending_tournament_invites(db, user_id)
    active_tournaments = get_active_tournaments(db, user_id)
    past_tournaments = get_past_tournaments(db, user_id)

    # Fetch user data if needed (e.g. for API)
    user_data = get_user_by_id(db, user_id)

    return {
        "user": user_data,
        "matches": matches,
        "stats": stats,
        "friends": friends,
        "requests": requests_data,
        "group_rankings": group_rankings,
        "pending_tournament_invites": pending_tournament_invites,
        "active_tournaments": active_tournaments,
        "past_tournaments": past_tournaments,
    }
