"""Helper functions for user-related data."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pickaladder.utils import mask_email

from .models import User, UserSession

if TYPE_CHECKING:
    from typing import Any


def calculate_vanity_metrics(user_stats: dict[str, Any] | None) -> dict[str, Any]:
    """Calculate vanity metrics (wins, losses, win_rate) from user stats.

    Handles type conversion and zero-division cases.
    """
    if not user_stats:
        user_stats = {}

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

    return {
        "wins": wins,
        "losses": losses,
        "total_games": total_games,
        "win_rate": win_rate,
    }


def calculate_onboarding_progress(
    user_data: dict[str, Any],
    matches_count: int,
    group_rankings_count: int,
    friends_count: int,
) -> dict[str, Any]:
    """Calculate onboarding progress markers and percentage."""
    has_avatar = bool(user_data.get("profilePictureUrl"))
    has_dupr = bool(user_data.get("duprRating") or user_data.get("dupr_rating"))
    has_match = matches_count > 0
    has_group = group_rankings_count > 0
    has_friend = friends_count > 0

    steps = [has_avatar, has_dupr, has_match, has_group, has_friend]
    percent = int((sum(steps) / len(steps)) * 100)

    return {
        "has_avatar": has_avatar,
        "has_dupr": has_dupr,
        "has_rating": has_dupr,
        "has_match": has_match,
        "has_group": has_group,
        "has_friend": has_friend,
        "percent": percent,
    }


def extract_match_results_for_streak(
    recent_docs: list[Any], user_id: str
) -> list[dict[str, bool]]:
    """Extract user_won flag from match documents for streak calculation."""
    from pickaladder.user.services.match_stats import _get_user_match_won_lost

    processed = []
    for doc in recent_docs:
        d = doc.to_dict() or {}
        won, _ = _get_user_match_won_lost(d, user_id)
        processed.append({"user_won": won})
    return processed


def wrap_user(
    user_data: dict[str, Any] | User | None, uid: str | None = None
) -> UserSession | None:
    """Wrap a user dictionary in a UserSession model object.

    Args:
        user_data: The user data dictionary from Firestore or a User TypedDict.
        uid: Optional user ID if not present in user_data.

    Returns:
        A UserSession model object or None if user_data is None.
    """
    if user_data is None:
        return None
    if isinstance(user_data, UserSession):
        return user_data

    data = dict(user_data)
    if uid:
        data["uid"] = uid
    return UserSession(data)


def smart_display_name(user: dict[str, Any] | User) -> str:
    """Return a smart display name for a user.

    If the user is a ghost user (is_ghost is True or username starts with 'ghost_'):
    - Prioritize the name field.
    - Fallback to a masked version of the email if available.
    - Default to 'Pending Invite' if both are missing.
    Regular users default to their username.
    """
    username = user.get("username", "")
    name = user.get("name")
    is_ghost = user.get("is_ghost") or username.startswith("ghost_")

    if is_ghost:
        if name:
            return name
        email = user.get("email")
        if email:
            return mask_email(email)
        return "Pending Invite"

    return username or name or "Unknown Player"
