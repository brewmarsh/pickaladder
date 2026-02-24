from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, cast

from .stats_utils import (
    _get_team_ids_from_match,
    _get_user_match_won_lost,
)

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client

    from ..models import User


def get_user_matches(
    db: Client, user_id: str, limit: int | None = None
) -> list[DocumentSnapshot]:
    """Fetch matches involving a user."""
    from firebase_admin import firestore

    matches_ref = db.collection("matches")
    query = matches_ref.where(
        filter=firestore.FieldFilter("participants", "array_contains", user_id)
    ).order_by("matchDate", direction=firestore.Query.DESCENDING)

    if limit:
        query = query.limit(limit)

    return list(query.stream())


def _process_match_for_streak(m: Any, user_id: str) -> dict[str, Any] | None:
    """Extract result and date information from a match object."""
    if hasattr(m, "to_dict"):
        data = m.to_dict()
        date = data.get("matchDate") if data else None
        if date is None:
            date = getattr(m, "create_time", None)
    else:
        data = m
        date = data.get("matchDate") or data.get("date")

    if not data:
        return None

    won, lost = _get_user_match_won_lost(data, user_id)
    return {"won": won, "lost": lost, "date": date}


def _get_processed_streak_items(
    user_id: str, matches: list[Any]
) -> list[dict[str, Any]]:
    """Helper to process matches for streak calculation."""
    processed = []
    for m in matches:
        if item := _process_match_for_streak(m, user_id):
            processed.append(item)
    return processed


def _sort_streak_items(processed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort processed match items by date descending."""
    return sorted(
        processed,
        key=lambda x: x["date"] if x.get("date") else datetime.datetime.min,
        reverse=True,
    )


def _calculate_win_streak_count(processed: list[dict[str, Any]]) -> int:
    """Iterate through matches and count consecutive wins."""
    streak = 0
    for m in processed:
        if m.get("won"):
            streak += 1
        elif m.get("lost"):
            break
    return streak


def calculate_current_streak(user_id: str, matches: list[Any]) -> int:
    """Calculate current win streak for a user."""
    processed = _get_processed_streak_items(user_id, matches)
    sorted_items = _sort_streak_items(processed)
    return _calculate_win_streak_count(sorted_items)


def _get_opponent_id_from_match(data: dict[str, Any], user_id: str) -> str | None:
    """Extract opponent ID from a singles match."""
    if not data or data.get("matchType") == "doubles":
        return None

    p1_ref, p2_ref = data.get("player1Ref"), data.get("player2Ref")
    if p1_ref and p1_ref.id == user_id:
        return p2_ref.id if p2_ref else None
    if p2_ref and p2_ref.id == user_id:
        return p1_ref.id if p1_ref else None
    return None


def _get_opponent_ids(matches: list[Any], user_id: str, limit: int) -> list[str]:
    """Helper to collect unique opponent IDs from matches."""
    opponent_ids: list[str] = []
    for m in matches:
        data = m.to_dict() if hasattr(m, "to_dict") else m
        opp_id = _get_opponent_id_from_match(data, user_id)
        if opp_id and opp_id not in opponent_ids:
            opponent_ids.append(opp_id)
        if len(opponent_ids) >= limit:
            break
    return opponent_ids


def _fetch_opponents_map(
    db: Client, opponent_ids: list[str]
) -> dict[str, dict[str, Any]]:
    """Fetch user data for multiple opponent IDs."""
    if not opponent_ids:
        return {}
    refs = [db.collection("users").document(oid) for oid in opponent_ids]
    opponents_map = {}
    for doc in db.get_all(refs):
        if doc.exists and (d := doc.to_dict()):
            d["id"] = d["uid"] = doc.id
            opponents_map[doc.id] = d
    return opponents_map


def get_recent_opponents(
    db: Client, user_id: str, matches: list[Any], limit: int = 4
) -> list[User]:
    """Identify recent unique 1v1 opponents."""
    opponent_ids = _get_opponent_ids(matches, user_id, limit)
    opp_map = _fetch_opponents_map(db, opponent_ids)
    return [cast("User", opp_map[oid]) for oid in opponent_ids if oid in opp_map]


def _calculate_streak(processed: list[dict[str, Any]]) -> tuple[int, str]:
    """Calculate current streak from processed matches."""
    if not processed:
        return 0, "N/A"

    last_won = processed[0]["user_won"]
    streak_type = "W" if last_won else "L"
    current_streak = 0
    for m in processed:
        if m["user_won"] == last_won:
            current_streak += 1
        else:
            break
    return current_streak, streak_type


def _process_match_stats_item(match_doc: DocumentSnapshot, user_id: str) -> dict | None:
    """Extract win/loss and metadata for a single match for stats calculation."""
    data = match_doc.to_dict()
    if not data:
        return None
    won, lost = _get_user_match_won_lost(data, user_id)
    return {
        "doc": match_doc,
        "data": data,
        "won": won,
        "lost": lost,
        "date": data.get("matchDate") or match_doc.create_time,
    }


def _process_stats_batch(
    matches: list[DocumentSnapshot], user_id: str
) -> tuple[int, int, list[dict[str, Any]]]:
    """Process a list of match documents and count wins/losses."""
    wins = losses = 0
    processed = []
    for doc in matches:
        if item := _process_match_stats_item(doc, user_id):
            wins += 1 if item["won"] else 0
            losses += 1 if item["lost"] else 0
            processed.append(
                {
                    "doc": item["doc"],
                    "data": item["data"],
                    "user_won": item["won"],
                    "date": item["date"],
                }
            )
    return wins, losses, processed


def _format_stats_response(
    wins: int, losses: int, processed: list[dict[str, Any]]
) -> dict[str, Any]:
    """Format the final statistics dictionary."""
    total = wins + losses
    processed.sort(key=lambda x: x["date"] or datetime.datetime.min, reverse=True)
    streak, s_type = _calculate_streak(processed)

    return {
        "wins": wins,
        "losses": losses,
        "total_games": total,
        "win_rate": (wins / total * 100) if total > 0 else 0,
        "current_streak": streak,
        "streak_type": s_type,
        "processed_matches": processed,
    }


def calculate_stats(matches: list[DocumentSnapshot], user_id: str) -> dict[str, Any]:
    """Calculate aggregate performance statistics from a list of matches."""
    wins, losses, processed = _process_stats_batch(matches, user_id)
    return _format_stats_response(wins, losses, processed)


def _get_h2h_match_data(
    data: dict[str, Any],
) -> tuple[tuple[int, int], tuple[set[str], set[str]]]:
    """Extract scores and team IDs from match data."""
    scores = (int(data.get("player1Score", 0)), int(data.get("player2Score", 0)))
    team_ids = _get_team_ids_from_match(data)
    return scores, team_ids


def _calculate_h2h_delta(
    u1: str, u2: str, teams: tuple[set[str], set[str]], scores: tuple[int, int]
) -> tuple[int, int, int]:
    """Calculate win, loss, and point delta for user 1 in a specific matchup."""
    t1, t2 = teams
    s1, s2 = scores
    if u1 in t1 and u2 in t2:
        return (1 if s1 > s2 else 0), (1 if s1 < s2 else 0), (s1 - s2)
    if u1 in t2 and u2 in t1:
        return (1 if s2 > s1 else 0), (1 if s2 < s1 else 0), (s2 - s1)
    return 0, 0, 0


def _process_h2h_match(
    data: dict[str, Any] | None, user_id_1: str, user_id_2: str
) -> tuple[int, int, int]:
    """Process a single match for H2H stats."""
    if not data or user_id_2 not in data.get("participants", []):
        return 0, 0, 0

    scores, team_ids = _get_h2h_match_data(data)
    if scores[0] == scores[1]:
        return 0, 0, 0

    return _calculate_h2h_delta(user_id_1, user_id_2, team_ids, scores)


def get_h2h_stats(db: Client, user_id_1: str, user_id_2: str) -> dict[str, Any] | None:
    """Fetch head-to-head statistics between two users."""
    from firebase_admin import firestore

    wins = losses = points = 0
    query = db.collection("matches").where(
        filter=firestore.FieldFilter("participants", "array_contains", user_id_1)
    )

    for match in query.stream():
        w, l_count, p_diff = _process_h2h_match(match.to_dict(), user_id_1, user_id_2)
        wins, losses, points = wins + w, losses + l_count, points + p_diff

    return (
        {"wins": wins, "losses": losses, "point_diff": points}
        if (wins > 0 or losses > 0)
        else None
    )


def _get_profile_match_alignment(
    match_dict: dict[str, Any], user_id: str
) -> dict[str, Any]:
    """Stub for missing function."""
    return {}
