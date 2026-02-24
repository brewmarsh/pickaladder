from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, cast

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


def _get_team_ids_from_match(data: dict[str, Any]) -> tuple[set[str], set[str]]:
    """Extract team 1 and team 2 member IDs from a match."""
    if data.get("matchType") == "doubles":

        def get_ids(k: str) -> set[str]:
            return {str(r.id if hasattr(r, "id") else r) for r in data.get(k, []) if r}

        return get_ids("team1"), get_ids("team2")

    p1_ref, p2_ref = data.get("player1Ref"), data.get("player2Ref")
    p1_data, p2_data = data.get("player_1_data", {}), data.get("player_2_data", {})

    id1 = str(
        (p1_ref.id if p1_ref is not None and hasattr(p1_ref, "id") else "")
        or p1_data.get("uid")
        or data.get("player1Id")
        or ""
    )
    id2 = str(
        (p2_ref.id if p2_ref is not None and hasattr(p2_ref, "id") else "")
        or p2_data.get("uid")
        or data.get("player2Id")
        or ""
    )

    return {id1}, {id2}


def _get_user_match_won_lost(
    match_data: dict[str, Any], user_id: str
) -> tuple[bool, bool]:
    """Determine if the user won or lost the match, including handling of draws."""
    p1_score = int(match_data.get("player1Score", 0))
    p2_score = int(match_data.get("player2Score", 0))

    if p1_score == p2_score:
        return False, False

    t1_ids, t2_ids = _get_team_ids_from_match(match_data)
    if user_id in t1_ids:
        return (p1_score > p2_score), (p1_score < p2_score)
    if user_id in t2_ids:
        return (p2_score > p1_score), (p2_score < p1_score)

    return False, False


def _get_user_match_result(
    match_dict: dict[str, Any], user_id: str, winner_slot: str
) -> str:
    """Determine if the user won or lost the match."""
    won, lost = _get_user_match_won_lost(match_dict, user_id)
    if won:
        return "win"
    if lost:
        return "loss"
    return "draw"


def _get_match_winner_slot(match_dict: dict[str, Any]) -> str:
    """Determine the winner slot ('team1' or 'team2')."""
    p1_score = match_dict.get("player1Score", 0)
    p2_score = match_dict.get("player2Score", 0)
    return "team1" if p1_score > p2_score else "team2"


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


def calculate_current_streak(user_id: str, matches: list[Any]) -> int:
    """Calculate current win streak for a user."""
    processed = []
    for m in matches:
        if item := _process_match_for_streak(m, user_id):
            processed.append(item)

    processed.sort(
        key=lambda x: x["date"] if x.get("date") else datetime.datetime.min,
        reverse=True,
    )

    streak = 0
    for m in processed:
        if m.get("won"):
            streak += 1
        elif m.get("lost"):
            break
    return streak


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


def get_recent_opponents(
    db: Client, user_id: str, matches: list[Any], limit: int = 4
) -> list[User]:
    """Identify recent unique 1v1 opponents."""
    opponent_ids: list[str] = []
    for m in matches:
        data = m.to_dict() if hasattr(m, "to_dict") else m
        opp_id = _get_opponent_id_from_match(data, user_id)
        if opp_id and opp_id not in opponent_ids:
            opponent_ids.append(opp_id)
        if len(opponent_ids) >= limit:
            break

    if not opponent_ids:
        return []

    refs = [db.collection("users").document(oid) for oid in opponent_ids]
    opponents_map = {}
    for doc in db.get_all(refs):
        if doc.exists and (d := doc.to_dict()):
            d["id"] = d["uid"] = doc.id
            opponents_map[doc.id] = d

    return [
        cast("User", opponents_map[oid]) for oid in opponent_ids if oid in opponents_map
    ]


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


def calculate_stats(matches: list[DocumentSnapshot], user_id: str) -> dict[str, Any]:
    """Calculate aggregate performance statistics from a list of matches."""
    wins = losses = 0
    processed = []

    for match_doc in matches:
        if match_data := match_doc.to_dict():
            won, lost = _get_user_match_won_lost(match_data, user_id)
            wins, losses = wins + (1 if won else 0), losses + (1 if lost else 0)
            processed.append(
                {
                    "doc": match_doc,
                    "data": match_data,
                    "user_won": won,
                    "date": match_data.get("matchDate") or match_doc.create_time,
                }
            )

    total = wins + losses
    win_rate = (wins / total) * 100 if total > 0 else 0
    processed.sort(key=lambda x: x["date"] or datetime.datetime.min, reverse=True)
    streak, s_type = _calculate_streak(processed)

    return {
        "wins": wins,
        "losses": losses,
        "total_games": total,
        "win_rate": win_rate,
        "current_streak": streak,
        "streak_type": s_type,
        "processed_matches": processed,
    }


def _get_h2h_match_data(
    data: dict[str, Any],
) -> tuple[tuple[int, int], tuple[set[str], set[str]]]:
    """Extract scores and team IDs from match data."""
    scores = (int(data.get("player1Score", 0)), int(data.get("player2Score", 0)))
    team_ids = _get_team_ids_from_match(data)
    return scores, team_ids


def get_h2h_stats(db: Client, user_id_1: str, user_id_2: str) -> dict[str, Any] | None:
    """Fetch head-to-head statistics between two users."""
    from firebase_admin import firestore

    wins = losses = points = 0
    query = db.collection("matches").where(
        filter=firestore.FieldFilter("participants", "array_contains", user_id_1)
    )

    for match in query.stream():
        if data := match.to_dict():
            if user_id_2 in data.get("participants", []):
                scores, team_ids = _get_h2h_match_data(data)
                if scores[0] == scores[1]:
                    continue
                p1_score, p2_score = scores
                t1_ids, t2_ids = team_ids

                w = l_count = p_diff = 0
                if user_id_1 in t1_ids and user_id_2 in t2_ids:
                    w, l_count, p_diff = (
                        (1 if p1_score > p2_score else 0),
                        (1 if p1_score < p2_score else 0),
                        (p1_score - p2_score),
                    )
                elif user_id_1 in t2_ids and user_id_2 in t1_ids:
                    w, l_count, p_diff = (
                        (1 if p2_score > p1_score else 0),
                        (1 if p2_score < p1_score else 0),
                        (p2_score - p1_score),
                    )
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
