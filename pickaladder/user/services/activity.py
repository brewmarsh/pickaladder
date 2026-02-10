from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any

from pickaladder.user.services import firestore as service_firestore

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client


def get_user_groups(db: Client, user_id: str) -> list[dict[str, Any]]:
    """Fetch all groups the user is a member of."""
    user_ref = db.collection("users").document(user_id)
    groups_query = (
        db.collection("groups")
        .where("members", "array_contains", user_ref)
        .stream()
    )
    groups = []
    for doc in groups_query:
        data = doc.to_dict()
        if data:
            data["id"] = doc.id
            groups.append(data)
    return groups


def get_pending_tournament_invites(db: Client, user_id: str) -> list[dict[str, Any]]:
    """Fetch pending tournament invites for a user."""
    if not user_id:
        return []
    try:
        tournaments_query = (
            db.collection("tournaments")
            .where(
                    "participant_ids", "array_contains", user_id
                )
            .stream()
        )

        pending_invites = []
        for doc in tournaments_query:
            data = doc.to_dict()
            if data:
                participants = data.get("participants") or []
                for p in participants:
                    if not p:
                        continue
                    p_ref = p.get("userRef")
                    p_uid = p_ref.id if p_ref else p.get("user_id")
                    if p_uid == user_id and p.get("status") == "pending":
                        data["id"] = doc.id
                        pending_invites.append(data)
                        break
        return pending_invites
    except TypeError:
        # Handle mockfirestore bug when array field is None
        return []


def get_active_tournaments(db: Client, user_id: str) -> list[dict[str, Any]]:
    """Fetch active tournaments for a user."""
    tournaments_query = (
        db.collection("tournaments")
        .where(
                "participant_ids", "array_contains", user_id
            )
        .stream()
    )
    active_tournaments = []
    for doc in tournaments_query:
        data = doc.to_dict()
        if data and data.get("status") in ["Active", "Scheduled"]:
            participants = data.get("participants") or []
            for p in participants:
                if not p:
                    continue
                p_uid = p.get("userRef").id if p.get("userRef") else p.get("user_id")
                if p_uid == user_id and p.get("status") == "accepted":
                    data["id"] = doc.id
                    # Format date for display
                    raw_date = data.get("date")
                    if raw_date is not None:
                        if hasattr(raw_date, "to_datetime"):
                            data["date_display"] = raw_date.to_datetime().strftime(
                                "%b %d, %Y"
                            )
                        elif isinstance(raw_date, datetime.datetime):
                            data["date_display"] = raw_date.strftime("%b %d, %Y")
                    active_tournaments.append(data)
                    break
    # Sort by date ascending (soonest first)
    active_tournaments.sort(key=lambda x: x.get("date") or datetime.datetime.max)
    return active_tournaments


def get_past_tournaments(db: Client, user_id: str) -> list[dict[str, Any]]:
    """Fetch past (completed) tournaments for a user."""
    from pickaladder.tournament.utils import get_tournament_standings

    tournaments_query = (
        db.collection("tournaments")
        .where(
                "participant_ids", "array_contains", user_id
            )
        .stream()
    )
    past_tournaments = []
    for doc in tournaments_query:
        data = doc.to_dict()
        if data and data.get("status") == "Completed":
            data["id"] = doc.id
            # Find winner
            match_type = data.get("matchType", "singles")
            standings = get_tournament_standings(db, doc.id, match_type)
            data["winner_name"] = standings[0]["name"] if standings else "TBD"

            raw_date = data.get("date")
            if raw_date is not None:
                if hasattr(raw_date, "to_datetime"):
                    data["date_display"] = raw_date.to_datetime().strftime("%b %d, %Y")
                elif isinstance(raw_date, datetime.datetime):
                    data["date_display"] = raw_date.strftime("%b %d, %Y")

            past_tournaments.append(data)

    # Sort by date descending
    past_tournaments.sort(
        key=lambda x: x.get("date") or datetime.datetime.min, reverse=True
    )
    return past_tournaments


def get_public_groups(db: Client, limit: int = 10) -> list[dict[str, Any]]:
    """Fetch a list of public groups, enriched with owner data."""
    # Query for public groups
    public_groups_query = (
        db.collection("groups")
        .where("is_public", "==", True)
        .order_by("createdAt", direction=service_firestore.Query.DESCENDING)
        .limit(limit)
    )
    public_group_docs = list(public_groups_query.stream())

    # Enrich groups with owner data
    owner_refs = []
    for doc in public_group_docs:
        data = doc.to_dict()
        if data and (ref := data.get("ownerRef")):
            owner_refs.append(ref)
    unique_owner_refs = list({ref for ref in owner_refs if ref})

    owners_data = {}
    if unique_owner_refs:
        owner_docs = db.get_all(unique_owner_refs)
        owners_data = {doc.id: doc.to_dict() for doc in owner_docs if doc.exists}

    guest_user = {"username": "Guest", "id": "unknown"}

    enriched_groups = []
    for doc in public_group_docs:
        data = doc.to_dict()
        if data is None:
            continue
        data["id"] = doc.id
        owner_ref = data.get("ownerRef")
        if owner_ref and owner_ref.id in owners_data:
            data["owner"] = owners_data[owner_ref.id]
        else:
            data["owner"] = guest_user
        enriched_groups.append(data)

    return enriched_groups


def get_group_rankings(db: Client, user_id: str) -> list[dict[str, Any]]:
    """Fetch group rankings for a user."""
    from pickaladder.group.utils import (  # noqa: PLC0415
        get_group_leaderboard,
    )

    user_ref = db.collection("users").document(user_id)
    group_rankings = []
    my_groups_query = (
        db.collection("groups")
        .where("members", "array_contains", user_ref)
        .stream()
    )
    for group_doc in my_groups_query:
        group_data = group_doc.to_dict()
        if group_data is None:
            continue
        leaderboard = get_group_leaderboard(group_doc.id)
        user_ranking_data = None
        for i, player in enumerate(leaderboard):
            if player["id"] == user_id:
                rank = i + 1
                user_ranking_data = {
                    "group_id": group_doc.id,
                    "group_name": group_data.get("name", "N/A"),
                    "rank": rank,
                    "points": player.get("avg_score", 0),
                    "form": player.get("form", []),
                }
                if i > 0:
                    player_above = leaderboard[i - 1]
                    user_ranking_data["player_above"] = player_above.get("name")
                    user_ranking_data["points_to_overtake"] = player_above.get(
                        "avg_score", 0
                    ) - player.get("avg_score", 0)
                break

        if user_ranking_data:
            group_rankings.append(user_ranking_data)
        else:
            group_rankings.append(
                {
                    "group_id": group_doc.id,
                    "group_name": group_data.get("name", "N/A"),
                    "rank": "N/A",
                    "points": 0,
                    "form": [],
                }
            )
    return group_rankings


def get_user_profile_data(
    db: Client, current_user_id: str, target_user_id: str
) -> dict[str, Any] | None:
    """Fetch all data for a user's public profile."""
    from .core import get_user_by_id
    from .friendship import get_friendship_info, get_user_friends
    from .match_stats import (
        calculate_stats,
        format_matches_for_dashboard,
        get_h2h_stats,
        get_user_matches,
    )

    profile_user_data = get_user_by_id(db, target_user_id)
    if not profile_user_data:
        return None

    is_friend, friend_request_sent = get_friendship_info(
        db, current_user_id, target_user_id
    )

    h2h_stats = None
    if current_user_id != target_user_id:
        h2h_stats = get_h2h_stats(db, current_user_id, target_user_id)

    matches = get_user_matches(db, target_user_id)
    stats = calculate_stats(matches, target_user_id)
    display_items_docs = [m["doc"] for m in stats["processed_matches"][:20]]
    matches_data = format_matches_for_dashboard(db, display_items_docs, target_user_id)

    return {
        "profile_user": profile_user_data,
        "is_friend": is_friend,
        "friend_request_sent": friend_request_sent,
        "h2h_stats": h2h_stats,
        "friends": get_user_friends(db, target_user_id, limit=10),
        "matches": matches_data,
        "stats": stats,
    }


def get_community_data(db: Client, user_id: str, search_term: str) -> dict[str, Any]:
    """Fetch and filter community hub data."""
    from .core import get_all_users
    from .friendship import (
        get_user_friends,
        get_user_pending_requests,
        get_user_sent_requests,
    )

    friends = get_user_friends(db, user_id)
    incoming_requests = get_user_pending_requests(db, user_id)
    outgoing_requests = get_user_sent_requests(db, user_id)

    exclude_ids = [user_id]
    exclude_ids.extend([f["id"] for f in friends])
    exclude_ids.extend([r["id"] for r in incoming_requests])
    exclude_ids.extend([r["id"] for r in outgoing_requests])

    all_users = get_all_users(db, exclude_ids, limit=20)
    public_groups = get_public_groups(db, limit=10)
    pending_tournament_invites = get_pending_tournament_invites(db, user_id)

    if search_term:
        term = search_term.lower()

        def matches_search(u: dict[str, Any]) -> bool:
            return (
                term in u.get("username", "").lower()
                or term in u.get("name", "").lower()
                or term in u.get("email", "").lower()
            )

        friends = [f for f in friends if matches_search(f)]
        incoming_requests = [r for r in incoming_requests if matches_search(r)]
        outgoing_requests = [r for r in outgoing_requests if matches_search(r)]
        all_users = [u for u in all_users if matches_search(u)]
        pending_tournament_invites = [
            ti
            for ti in pending_tournament_invites
            if term in ti.get("name", "").lower()
        ]
        public_groups = [
            g
            for g in public_groups
            if term in g.get("name", "").lower()
            or term in g.get("description", "").lower()
        ]

    return {
        "friends": friends,
        "incoming_requests": incoming_requests,
        "outgoing_requests": outgoing_requests,
        "all_users": all_users,
        "public_groups": public_groups,
        "pending_tournament_invites": pending_tournament_invites,
    }
