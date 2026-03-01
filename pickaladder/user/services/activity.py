from __future__ import annotations

from typing import TYPE_CHECKING, Any

from firebase_admin import firestore

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client


def _extract_unique_owner_refs(public_group_docs: list[Any]) -> list[Any]:
    """Gather unique owner references from a list of group documents."""
    owner_refs = []
    for doc in public_group_docs:
        data = doc.to_dict()
        if data and (ref := data.get("ownerRef")):
            owner_refs.append(ref)
    return list({ref for ref in owner_refs if ref})


def _map_owner_docs_to_data(owner_docs: list[Any]) -> dict[str, dict[str, Any]]:
    """Map owner document snapshots to sanitized data dictionaries."""
    from .core import _sanitize_user_data

    owners_data = {}
    for doc in owner_docs:
        if doc.exists:
            data = doc.to_dict() or {}
            data["id"] = doc.id
            owners_data[doc.id] = _sanitize_user_data(data)
    return owners_data


def _fetch_owners_data(
    db: Client, public_group_docs: list[Any]
) -> dict[str, dict[str, Any]]:
    """Fetch sanitized data for all unique owners in a list of group documents."""
    unique_owner_refs = _extract_unique_owner_refs(public_group_docs)
    if not unique_owner_refs:
        return {}

    owner_docs = list(db.get_all(unique_owner_refs))
    return _map_owner_docs_to_data(owner_docs)


def _enrich_group_with_owner(
    data: dict[str, Any], doc_id: str, owners_data: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Enrich group data with owner information."""
    guest_user = {"username": "Guest", "id": "unknown"}
    data["id"] = doc_id
    owner_ref = data.get("ownerRef")
    if (
        owner_ref is not None
        and hasattr(owner_ref, "id")
        and owner_ref.id in owners_data
    ):
        data["owner"] = owners_data[owner_ref.id]
    else:
        data["owner"] = guest_user
    return data


def _build_ranking_data(
    group_id: str,
    group_data: dict[str, Any],
    player: dict[str, Any],
    rank: int | str,
) -> dict[str, Any]:
    """Build the base ranking data dictionary."""
    return {
        "group_id": group_id,
        "group_name": group_data.get("name", "N/A"),
        "group_image": group_data.get("profilePictureUrl"),
        "rank": rank,
        "points": player.get("avg_score", 0),
        "form": player.get("form", []),
    }


def _enrich_with_player_above(
    ranking_data: dict[str, Any], player: dict[str, Any], player_above: dict[str, Any]
) -> None:
    """Add details about the player ranked immediately above."""
    ranking_data["player_above"] = player_above.get("name")
    ranking_data["points_to_overtake"] = player_above.get("avg_score", 0) - player.get(
        "avg_score", 0
    )


def _calculate_user_ranking(
    user_id: str,
    leaderboard: list[dict[str, Any]],
    group_id: str,
    group_data: dict[str, Any],
) -> dict[str, Any]:
    """Calculate user ranking details from a leaderboard."""
    for i, player in enumerate(leaderboard):
        if player["id"] == user_id:
            ranking_data = _build_ranking_data(group_id, group_data, player, i + 1)
            if i > 0:
                _enrich_with_player_above(ranking_data, player, leaderboard[i - 1])
            return ranking_data

    return {
        "group_id": group_id,
        "group_name": group_data.get("name", "N/A"),
        "rank": "N/A",
        "points": 0,
        "form": [],
    }


def get_public_groups(db: Client, limit: int = 10) -> list[dict[str, Any]]:
    """Fetch a list of public groups, enriched with owner data."""
    # Query for public groups
    public_groups_query = (
        db.collection("groups")
        .where(filter=firestore.FieldFilter("is_public", "==", True))
        .order_by("createdAt", direction=firestore.Query.DESCENDING)
        .limit(limit)
    )
    public_group_docs = list(public_groups_query.stream())
    owners_data = _fetch_owners_data(db, public_group_docs)

    enriched_groups = []
    for doc in public_group_docs:
        data = doc.to_dict()
        if data is not None:
            enriched_groups.append(_enrich_group_with_owner(data, doc.id, owners_data))

    return enriched_groups


def get_user_groups(db: Client, user_id: str) -> list[dict[str, Any]]:
    """Fetch all groups a user belongs to."""
    user_ref = db.collection("users").document(user_id)
    groups_query = (
        db.collection("groups")
        .where(filter=firestore.FieldFilter("members", "array_contains", user_ref))
        .stream()
    )
    groups = []
    for doc in groups_query:
        data = doc.to_dict()
        if data:
            data["id"] = doc.id
            groups.append(data)
    return groups


def get_group_rankings(db: Client, user_id: str) -> list[dict[str, Any]]:
    """Fetch group rankings for a user."""
    from pickaladder.group.utils import get_group_leaderboard

    user_ref = db.collection("users").document(user_id)
    group_rankings = []
    my_groups_query = (
        db.collection("groups")
        .where(filter=firestore.FieldFilter("members", "array_contains", user_ref))
        .stream()
    )
    for group_doc in my_groups_query:
        group_data = group_doc.to_dict()
        if group_data is None:
            continue
        leaderboard = get_group_leaderboard(group_doc.id)
        group_rankings.append(
            _calculate_user_ranking(user_id, leaderboard, group_doc.id, group_data)
        )
    return group_rankings


def _fetch_profile_stats(
    db: Client, target_user_id: str, profile_user_data: dict[str, Any]
) -> tuple[dict[str, Any], list[Any]]:
    """Fetch matches and calculate statistics for user profile."""
    from .match_stats import calculate_stats, get_user_matches

    all_matches = get_user_matches(db, target_user_id)
    stats = calculate_stats(all_matches, target_user_id)

    # Fetch limited matches for recent activity feed
    recent_matches = get_user_matches(db, target_user_id, limit=20)

    return stats, recent_matches


def get_user_profile_data(
    db: Client, current_user_id: str, target_user_id: str
) -> dict[str, Any] | None:
    """Fetch all data for a user's public profile."""
    from .core import get_user_by_id
    from .friendship import get_friendship_info, get_user_friends
    from .match_formatting import format_matches_for_dashboard
    from .match_stats import get_h2h_stats

    u_data = get_user_by_id(db, target_user_id)
    if not u_data:
        return None

    is_f, sent = get_friendship_info(db, current_user_id, target_user_id)
    h2h = (
        get_h2h_stats(db, current_user_id, target_user_id)
        if current_user_id != target_user_id
        else None
    )

    stats, matches = _fetch_profile_stats(db, target_user_id, u_data)
    matches_data = format_matches_for_dashboard(db, matches, target_user_id)

    return {
        "profile_user": u_data,
        "is_friend": is_f,
        "friend_request_sent": sent,
        "h2h_stats": h2h,
        "friends": get_user_friends(db, target_user_id, limit=10),
        "matches": matches_data,
        "stats": stats,
    }


def _matches_community_search(
    item: dict[str, Any], term: str, fields: list[str]
) -> bool:
    """Helper to check if any of the specified fields match the search term."""
    return any(term in str(item.get(f, "")).lower() for f in fields)


def _filter_community_list(
    items: list[dict[str, Any]], term: str, fields: list[str]
) -> list[dict[str, Any]]:
    """Filter a list of items based on a search term and fields."""
    if not term:
        return items
    return [i for i in items if _matches_community_search(i, term, fields)]


def get_community_data(db: Client, user_id: str, search_term: str) -> dict[str, Any]:
    """Fetch and filter community hub data."""
    from .core import get_all_users
    from .friendship import (
        get_user_friends,
        get_user_pending_requests,
        get_user_sent_requests,
    )
    from .user_tournament_service import get_pending_tournament_invites

    friends = get_user_friends(db, user_id)
    inc = get_user_pending_requests(db, user_id)
    out = get_user_sent_requests(db, user_id)

    exclude = [user_id] + [f["id"] for f in friends] + [r["id"] for r in inc + out]

    users = get_all_users(db, exclude, limit=20)
    groups = get_public_groups(db, limit=10)
    invites = get_pending_tournament_invites(db, user_id)

    term = search_term.lower() if search_term else ""
    u_fields = ["username", "name", "email"]
    return {
        "friends": _filter_community_list(friends, term, u_fields),
        "incoming_requests": _filter_community_list(inc, term, u_fields),
        "outgoing_requests": _filter_community_list(out, term, u_fields),
        "all_users": _filter_community_list(users, term, u_fields),
        "public_groups": _filter_community_list(groups, term, ["name", "description"]),
        "pending_tournament_invites": _filter_community_list(invites, term, ["name"]),
    }
