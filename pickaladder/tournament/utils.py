"""Utility functions for tournament management."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from firebase_admin import firestore

from pickaladder.user.utils import smart_display_name

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client


def fetch_tournament_matches(db: Client, tournament_id: str) -> Any:
    """Fetch all match documents associated with the tournament_id."""
    return (
        db.collection("matches")
        .where(filter=firestore.FieldFilter("tournamentId", "==", tournament_id))
        .stream()
    )


def aggregate_match_data(matches: Any, match_type: str) -> dict[str, dict[str, Any]]:
    """Iterate once through matches to build raw map of wins, losses, and point_diff."""
    standings: dict[str, dict[str, Any]] = {}

    for match in matches:
        data = match.to_dict()
        if not data:
            continue
        p1_score = data.get("player1Score", 0)
        p2_score = data.get("player2Score", 0)

        if match_type == "doubles":
            id1 = data.get("team1Id")
            id2 = data.get("team2Id")
        else:
            p1_ref = data.get("player1Ref")
            p2_ref = data.get("player2Ref")
            if not p1_ref or not p2_ref:
                continue
            id1 = p1_ref.id
            id2 = p2_ref.id

        if not id1 or not id2:
            continue

        for pid in [id1, id2]:
            if pid not in standings:
                standings[pid] = {
                    "id": pid,
                    "wins": 0,
                    "losses": 0,
                    "point_diff": 0,
                }

        if p1_score > p2_score:
            standings[id1]["wins"] += 1
            standings[id2]["losses"] += 1
        else:
            standings[id2]["wins"] += 1
            standings[id1]["losses"] += 1

        standings[id1]["point_diff"] += p1_score - p2_score
        standings[id2]["point_diff"] += p2_score - p1_score

    return standings


def sort_and_format_standings(
    db: Client, raw_standings: dict[str, dict[str, Any]], match_type: str
) -> list[dict[str, Any]]:
    """Convert the map to a list, enrich with names, and sort by tie-breaking rules."""
    standings_list = list(raw_standings.values())
    if not standings_list:
        return []

    if match_type == "doubles":
        for s in standings_list:
            team_doc = cast(
                "DocumentSnapshot", db.collection("teams").document(s["id"]).get()
            )
            t_data = team_doc.to_dict()
            s["name"] = (
                t_data.get("name", "Unknown Team")
                if team_doc.exists and t_data
                else "Unknown Team"
            )
    else:
        user_ids = [s["id"] for s in standings_list]
        user_refs = [db.collection("users").document(uid) for uid in user_ids]
        user_docs = cast(list["DocumentSnapshot"], db.get_all(user_refs))
        users_map = {doc.id: doc.to_dict() for doc in user_docs if doc.exists}
        for s in standings_list:
            user_data = users_map.get(s["id"])
            s["name"] = smart_display_name(user_data) if user_data else "Unknown Player"

    # Sort by wins (desc), losses (asc), then point_diff (desc)
    standings_list.sort(
        key=lambda x: (x["wins"], -x["losses"], x.get("point_diff", 0)), reverse=True
    )
    return standings_list


def get_tournament_standings(
    db: Client, tournament_id: str, match_type: str
) -> list[dict[str, Any]]:
    """Orchestrate the calculation of tournament standings."""
    matches = fetch_tournament_matches(db, tournament_id)
    raw_standings = aggregate_match_data(matches, match_type)
    return sort_and_format_standings(db, raw_standings, match_type)


def resolve_participants(
    db: Client, participant_objs: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Resolve raw participant objects into enriched participant data."""
    if not participant_objs:
        return []

    user_refs = [
        obj["userRef"]
        if "userRef" in obj
        else db.collection("users").document(obj["user_id"])
        for obj in participant_objs
        if "userRef" in obj or "user_id" in obj
    ]
    user_docs = db.get_all(user_refs)
    users_map = {
        doc.id: {**(doc.to_dict() or {}), "id": doc.id}
        for doc in user_docs
        if doc.exists
    }

    participants = []
    for obj in participant_objs:
        uid = obj["userRef"].id if "userRef" in obj else obj.get("user_id")
        if uid and uid in users_map:
            u_data = users_map[uid]
            participants.append(
                {
                    "user": u_data,
                    "status": obj.get("status", "pending"),
                    "display_name": smart_display_name(u_data),
                    "team_name": obj.get("team_name"),
                }
            )
    return participants


def get_invitable_users(
    db: Client, user_id: str, participant_objs: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Fetch and filter users that can be invited to a tournament."""
    user_ref = db.collection("users").document(user_id)

    # Source A: Friends
    friends_query = user_ref.collection("friends").stream()
    friend_ids = {doc.id for doc in friends_query}

    # Source B: Groups
    groups_query = (
        db.collection("groups")
        .where(filter=firestore.FieldFilter("members", "array_contains", user_ref))
        .stream()
    )
    group_member_ids = set()
    for group_doc in groups_query:
        g_data = group_doc.to_dict()
        if g_data and "members" in g_data:
            for m_ref in g_data["members"]:
                group_member_ids.add(m_ref.id)

    # Deduplicate & Filter: Remove current user and existing participants
    all_potential_ids = {str(uid) for uid in (friend_ids | group_member_ids)}
    all_potential_ids.discard(str(user_id))

    current_participant_ids = {
        str(obj["userRef"].id if "userRef" in obj else obj.get("user_id"))
        for obj in participant_objs
    }
    final_invitable_ids = all_potential_ids - current_participant_ids

    invitable_users = []
    if final_invitable_ids:
        u_refs = [db.collection("users").document(uid) for uid in final_invitable_ids]
        u_docs = db.get_all(u_refs)
        for u_doc in u_docs:
            if u_doc.exists:
                u_data = u_doc.to_dict()
                if u_data:
                    u_data["id"] = u_doc.id
                    invitable_users.append(u_data)

    invitable_users.sort(key=lambda u: smart_display_name(u).lower())
    return invitable_users
