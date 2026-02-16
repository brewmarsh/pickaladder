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
    """Fetch matches involving a user with descending date ordering."""
    from firebase_admin import firestore

    matches_ref = db.collection("matches")
    # Query using the participants array for O(1) user match lookup
    query = matches_ref.where("participants", "array_contains", user_id)

    try:
        query = query.order_by("matchDate", direction=firestore.Query.DESCENDING)
    except Exception:
        # Fallback for environments without the composite index
        pass

    if limit:
        query = query.limit(limit)

    return list(query.stream())

# ... (_get_player_info and _get_user_match_result remain unchanged)

def format_matches_for_dashboard(
    db: Client, matches: list[DocumentSnapshot], user_id: str
) -> list[dict[str, Any]]:
    """Format match documents for the dashboard UI with group match detection."""
    if not matches:
        return []

    # Batch fetch logic (Users, Teams, Tournaments) remains as in original file...
    # [Logic omitted for brevity - same as input]

    matches_data = []
    for match_doc in matches:
        m_data = match_doc.to_dict()
        if not m_data:
            continue

        match_dict = cast("dict[str, Any]", m_data)
        winner = _get_match_winner_slot(match_dict)
        user_result = _get_user_match_result(match_dict, user_id, winner)

        # Resolve player info and team names...
        # [Logic omitted for brevity - same as input]

        # RESOLVED CONFLICT: Robust check for group match using multiple key variants
        # and casting to integer for frontend compatibility
        is_group_match = 1 if (m_data.get("groupId") or m_data.get("group_id")) else 0

        matches_data.append(
            {
                "id": match_doc.id,
                "player1": p1_info,
                "player2": p2_info,
                "player1_score": m_data.get("player1Score", 0),
                "player2_score": m_data.get("player2Score", 0),
                "winner": winner,
                "date": date_str,
                "is_group_match": is_group_match,
                "match_type": m_data.get("matchType", "singles"),
                "user_result": user_result,
                "team1_name": t1_name,
                "team2_name": t2_name,
                "tournament_name": tournament_name,
                "created_by": m_data.get("createdBy"),
                "tournament_id": m_data.get("tournamentId"),
                "player_1_data": m_data.get("player_1_data"),
                "player_2_data": m_data.get("player_2_data"),
            }
        )
    return matches_data

# ... (Remaining helper methods like _get_user_match_won_lost and get_h2h_stats remain unchanged)