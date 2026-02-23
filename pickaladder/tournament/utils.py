"""Utility functions for tournament management."""

from __future__ import annotations

from typing import Any, cast

from firebase_admin import firestore

from pickaladder.user.helpers import smart_display_name


def fetch_tournament_matches(db: Any, tournament_id: str) -> Any:
    """Fetch all match documents associated with the tournament_id."""
    return (
        db.collection("matches")
        .where(filter=firestore.FieldFilter("tournamentId", "==", tournament_id))
        .stream()
    )


def _get_match_participant_ids(
    data: dict[str, Any], match_type: str
) -> tuple[str | None, str | None]:
    """Resolve player/team IDs from match data."""
    if match_type == "doubles":
        return data.get("team1Id"), data.get("team2Id")
    p1_ref = data.get("player1Ref")
    p2_ref = data.get("player2Ref")
    id1 = p1_ref.id if p1_ref else None
    id2 = p2_ref.id if p2_ref else None
    return id1, id2


def _record_match_result(standings: dict, id1: str, id2: str, s1: int, s2: int) -> None:
    """Update win/loss and point diff for two participants."""
    for pid in [id1, id2]:
        if pid not in standings:
            standings[pid] = {"id": pid, "wins": 0, "losses": 0, "point_diff": 0}

    if s1 > s2:
        standings[id1]["wins"] += 1
        standings[id2]["losses"] += 1
    else:
        standings[id2]["wins"] += 1
        standings[id1]["losses"] += 1

    standings[id1]["point_diff"] += s1 - s2
    standings[id2]["point_diff"] += s2 - s1


def aggregate_match_data(matches: Any, match_type: str) -> dict[str, dict[str, Any]]:
    """Iterate once through matches to build raw map of wins, losses, and point_diff."""
    standings: dict[str, dict[str, Any]] = {}
    for match in matches:
        data = cast(dict[str, Any], match.to_dict())
        if not data:
            continue
        id1, id2 = _get_match_participant_ids(data, match_type)
        if id1 and id2:
            s1, s2 = data.get("player1Score", 0), data.get("player2Score", 0)
            _record_match_result(standings, id1, id2, s1, s2)
    return standings


def _enrich_doubles_names(db: Any, standings: list[dict[str, Any]]) -> None:
    """Fetch and set team names for doubles standings."""
    for s in standings:
        doc = cast(Any, db.collection("teams").document(s["id"]).get())
        name = "Unknown Team"
        if doc.exists and (d := doc.to_dict()):
            name = d.get("name", "Unknown Team")
        s["name"] = name


def _enrich_singles_names(db: Any, standings: list[dict[str, Any]]) -> None:
    """Fetch and set user names for singles standings."""
    u_refs = [db.collection("users").document(s["id"]) for s in standings]
    u_docs = cast(list[Any], db.get_all(u_refs))
    u_map = {doc.id: doc.to_dict() for doc in u_docs if doc.exists}
    for s in standings:
        u_data = u_map.get(s["id"], {})
        u_data["id"] = s["id"]
        s["user"] = u_data
        s["name"] = smart_display_name(u_data) or "Unknown Player"
        s["display_name"] = s["name"]


def sort_and_format_standings(
    db: Any, raw_standings: dict[str, dict[str, Any]], match_type: str
) -> list[dict[str, Any]]:
    """Convert the map to a list, enrich with names, and sort."""
    standings_list = list(raw_standings.values())
    if not standings_list:
        return []
    if match_type == "doubles":
        _enrich_doubles_names(db, standings_list)
    else:
        _enrich_singles_names(db, standings_list)
    standings_list.sort(
        key=lambda x: (x["wins"], -x["losses"], x.get("point_diff", 0)), reverse=True
    )
    return standings_list


def get_tournament_standings(
    db: Any, tournament_id: str, match_type: str
) -> list[dict[str, Any]]:
    """Orchestrate the calculation of tournament standings."""
    matches = fetch_tournament_matches(db, tournament_id)
    raw = aggregate_match_data(matches, match_type)
    return sort_and_format_standings(db, raw, match_type)
