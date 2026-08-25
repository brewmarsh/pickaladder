"""Service for user dashboard data aggregation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pickaladder.teams.services import TeamService
from pickaladder.user.services.activity import (
    get_group_rankings,
    get_top_groups,
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
from pickaladder.user.services.user_tournament_service import (
    get_active_tournaments,
    get_past_tournaments,
    get_pending_tournament_invites,
)

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client


def get_dashboard_data(
    db: Client,
    user_id: str,
    include_activity: bool = False,
) -> dict[str, Any]:
    """Aggregate all data required for the user dashboard."""
    from pickaladder.user.helpers import calculate_onboarding_progress

    # 1. Fetch user and vanity stats (Keep synchronous as they are fast)
    user_data, vanity_metrics = _fetch_vanity_stats(db, user_id)

    # 2. Fetch match activity (Fast path: just check if matches exist for onboarding)
    total_matches = vanity_metrics.get("total_games", 0)

    match_data = (
        _fetch_recent_activity(db, user_id)
        if include_activity
        else {
            "matches": [],
            "next_cursor": None,
            "current_streak": 0,
            "streak_type": "",
            "recent_opponents": [],
        }
    )

    # 3. Fetch social and tournament data
    social_data = _fetch_social_and_tournaments(db, user_id)

    # 4. Calculate Onboarding Progress
    onboarding_progress = calculate_onboarding_progress(
        user_data,
        total_matches,
        len(social_data["group_rankings"]),
        len(social_data["friends"]),
    )

    # Assemble final stats object
    stats = {
        **vanity_metrics,
    }

    if include_activity:
        stats["processed_matches"] = [
            {"doc": d, "data": d.to_dict()} for d in match_data.get("recent_docs", [])
        ]

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
    db: Client,
    user_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Fetch user document and calculate vanity metrics."""
    from pickaladder.user.services.match_stats import calculate_stats, get_user_matches

    user_data = get_user_by_id(db, user_id) or {}
    all_matches = get_user_matches(db, user_id)
    vanity_metrics = calculate_stats(all_matches, user_id)

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
    import concurrent.futures

    # ⚡ Bolt Optimization:
    # What: Execute independent database queries concurrently.
    # Why: Resolves an N+1 latency bottleneck where each query waits for the previous one to complete.
    # Impact: Expected to reduce total latency for this aggregation block by ~4-6x.
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        f_friends = executor.submit(get_user_friends, db, user_id)
        f_requests = executor.submit(get_user_pending_requests, db, user_id)
        f_rankings = executor.submit(get_group_rankings, db, user_id)
        f_top_groups = executor.submit(get_top_groups, db, limit=3)
        f_top_teams = executor.submit(TeamService.get_top_teams, db, limit=3)
        f_invites = executor.submit(get_pending_tournament_invites, db, user_id)
        f_active = executor.submit(get_active_tournaments, db, user_id)
        f_past = executor.submit(get_past_tournaments, db, user_id)

        return {
            "friends": f_friends.result(),
            "requests": f_requests.result(),
            "group_rankings": f_rankings.result(),
            "top_groups": f_top_groups.result(),
            "top_teams": f_top_teams.result(),
            "pending_tournament_invites": f_invites.result(),
            "active_tournaments": f_active.result(),
            "past_tournaments": f_past.result(),
        }
