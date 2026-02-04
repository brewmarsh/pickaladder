"""Utility functions for tournament management."""

from __future__ import annotations

from typing import Any

from firebase_admin import firestore

from pickaladder.user.utils import smart_display_name


def fetch_tournament_matches(db: Any, tournament_id: str) -> Any:
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
    db: Any, raw_standings: dict[str, dict[str, Any]], match_type: str
) -> list[dict[str, Any]]:
    """Convert the map to a list, enrich with names, and sort by tie-breaking rules."""
    standings_list = list(raw_standings.values())
    if not standings_list:
        return []

    if match_type == "doubles":
        for s in standings_list:
            team_doc = db.collection("teams").document(s["id"]).get()
            s["name"] = (
                team_doc.to_dict().get("name", "Unknown Team")
                if team_doc.exists and team_doc.to_dict()
                else "Unknown Team"
            )
    else:
        user_ids = [s["id"] for s in standings_list]
        user_refs = [db.collection("users").document(uid) for uid in user_ids]
        user_docs = db.get_all(user_refs)
        users_map = {doc.id: doc.to_dict() for doc in user_docs if doc.exists}
        for s in standings_list:
            user_data = users_map.get(s["id"], {})
            s["name"] = smart_display_name(user_data) or "Unknown Player"

    # Sort by wins (desc), losses (asc), then point_diff (desc)
    standings_list.sort(
        key=lambda x: (x["wins"], -x["losses"], x.get("point_diff", 0)), reverse=True
    )
    return standings_list


def get_tournament_standings(
    db: Any, tournament_id: str, match_type: str
) -> list[dict[str, Any]]:
    """Orchestrate the calculation of tournament standings."""
    matches = fetch_tournament_matches(db, tournament_id)
    raw_standings = aggregate_match_data(matches, match_type)
    return sort_and_format_standings(db, raw_standings, match_type)
