"""Utility functions for tournament management."""

from __future__ import annotations

from typing import Any

from firebase_admin import firestore

from pickaladder.user.helpers import smart_display_name

# ... (fetch_tournament_matches and aggregate_match_data remain unchanged)

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
        users_map = {
            doc.id: {**(doc.to_dict() or {}), "id": doc.id}
            for doc in user_docs
            if doc.exists
        }
        
        for s in standings_list:
            # Merged safety and naming conventions
            user_data = users_map.get(
                s["id"], {"id": s["id"], "name": "Unknown Player"}
            )
            s["user"] = user_data
            s["name"] = smart_display_name(user_data) or "Unknown Player"
            
            # main branch addition for frontend component consistency
            s["display_name"] = s["name"]

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