from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client

    from pickaladder.user.models import UserRanking


def get_user_groups(db: Client, user_id: str) -> list[dict[str, Any]]:
    """Fetch all groups the user is a member of."""
    from pickaladder.user.services import firestore  # noqa: PLC0415

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


def get_pending_tournament_invites(db: Client, user_id: str) -> list[dict[str, Any]]:
    """Fetch pending tournament invites for a user."""
    from pickaladder.user.services import firestore  # noqa: PLC0415

    if not user_id:
        return []
    try:
        tournaments_query = (
            db.collection("tournaments")
            .where(
                filter=firestore.FieldFilter(
                    "participant_ids", "array_contains", user_id
                )
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
    from pickaladder.user.services import firestore  # noqa: PLC0415

    tournaments_query = (
        db.collection("tournaments")
        .where(
            filter=firestore.FieldFilter("participant_ids", "array_contains", user_id)
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
    from pickaladder.tournament.utils import (  # noqa: PLC0415
        get_tournament_standings,
    )
    from pickaladder.user.services import firestore  # noqa: PLC0415

    tournaments_query = (
        db.collection("tournaments")
        .where(
            filter=firestore.FieldFilter("participant_ids", "array_contains", user_id)
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
    from pickaladder.user.services import firestore  # noqa: PLC0415

    # Query for public groups
    public_groups_query = (
        db.collection("groups")
        .where(filter=firestore.FieldFilter("is_public", "==", True))
        .order_by("createdAt", direction=firestore.Query.DESCENDING)
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


def get_group_rankings(db: Client, user_id: str) -> list[UserRanking]:
    """Fetch group rankings for a user."""
    from typing import cast

    from pickaladder.group.utils import (  # noqa: PLC0415
        get_group_leaderboard,
    )
    from pickaladder.user.models import UserRanking  # noqa: PLC0415
    from pickaladder.user.services import firestore  # noqa: PLC0415

    user_ref = db.collection("users").document(user_id)
    group_rankings: list[UserRanking] = []
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
            group_rankings.append(cast(UserRanking, user_ranking_data))
        else:
            group_rankings.append(
                cast(
                    UserRanking,
                    {
                        "group_id": group_doc.id,
                        "group_name": group_data.get("name", "N/A"),
                        "rank": "N/A",
                        "points": 0,
                        "form": [],
                    },
                )
            )
    return group_rankings
