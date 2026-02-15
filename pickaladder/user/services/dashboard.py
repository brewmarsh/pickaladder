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
    _calculate_streak,
    _get_user_match_won_lost,
    format_matches_for_dashboard,
    get_recent_opponents,
    get_user_matches,
)

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client


def get_dashboard_data(db: Client, user_id: str) -> dict[str, Any]:
    """Aggregate all data required for the user dashboard."""
    # Fetch user data (includes stored stats for scalability)
    user_data = get_user_by_id(db, user_id) or {}
    user_stats = user_data.get("stats")
    if not isinstance(user_stats, dict):
        user_stats = {}

    # 1. Scalable Vanity Stats (from user document)
    wins = user_stats.get("wins", 0)
    losses = user_stats.get("losses", 0)

    # Ensure we have numbers (handles mocks in tests and potential None in DB)
    try:
        wins = int(wins) if wins is not None else 0
        losses = int(losses) if losses is not None else 0
    except (TypeError, ValueError):
        wins = 0
        losses = 0

    total_games = wins + losses
    win_rate = (wins / total_games * 100) if total_games > 0 else 0

    # 2. Scalable Match History (Limit to initial 20)
    recent_docs = get_user_matches(db, user_id, limit=20)
    matches = format_matches_for_dashboard(db, recent_docs, user_id)
    next_cursor = recent_docs[-1].id if recent_docs else None

    # 3. Calculate Engagement Stats from the recent batch
    processed = []
    for doc in recent_docs:
        d = doc.to_dict() or {}
        won, _ = _get_user_match_won_lost(d, user_id)
        processed.append({"user_won": won})

    current_streak, streak_type = _calculate_streak(processed)
    recent_opponents = get_recent_opponents(db, user_id, recent_docs)

    # Reconstruct a compatible stats object for the dashboard
    stats = {
        "wins": wins,
        "losses": losses,
        "total_games": total_games,
        "win_rate": win_rate,
        "current_streak": current_streak,
        "streak_type": streak_type,
        "processed_matches": [{"doc": d, "data": d.to_dict()} for d in recent_docs],
    }

    # Fetch other related data
    friends = get_user_friends(db, user_id)
    requests_data = get_user_pending_requests(db, user_id)
    group_rankings = get_group_rankings(db, user_id)
    pending_tournament_invites = get_pending_tournament_invites(db, user_id)
    active_tournaments = get_active_tournaments(db, user_id)
    past_tournaments = get_past_tournaments(db, user_id)

    # 4. Onboarding Progress calculation (Merged Logic)
    has_avatar = bool(user_data.get("profilePictureUrl") or user_data.get("avatar_url"))
    
    # Check for various DUPR field names across different schemas for robustness
    has_dupr = bool(
        user_data.get("dupr_id")
        or user_data.get("dupr_rating")
        or user_data.get("duprRating")
    )
    
    has_group = len(group_rankings) > 0
    has_match = len(matches) > 0
    has_friend = len(friends) > 0

    onboarding_steps = [has_avatar, has_dupr, has_group, has_match, has_friend]
    percent = int(sum(1 for step in onboarding_steps if step) / len(onboarding_steps) * 100)

    onboarding_progress = {
        "percent": percent,
        "has_avatar": has_avatar,
        "has_dupr": has_dupr,
        "has_rating": has_dupr,  # Template uses has_rating for the quest icon
        "has_group": has_group,
        "has_match": has_match,
        "has_friend": has_friend,
    }

    return {
        "user": user_data,
        "matches": matches,
        "next_cursor": next_cursor,
        "stats": stats,
        "current_streak": current_streak,
        "recent_opponents": recent_opponents,
        "friends": friends,
        "requests": requests_data,
        "group_rankings": group_rankings,
        "pending_tournament_invites": pending_tournament_invites,
        "active_tournaments": active_tournaments,
        "past_tournaments": past_tournaments,
        "onboarding_progress": onboarding_progress,
    }