from __future__ import annotations
from typing import TYPE_CHECKING, Any

def get_player_info(player_ref: Any, users_map: dict[str, Any]) -> dict[str, Any]:
    """Extract player info from a reference or dictionary."""
    if hasattr(player_ref, "id"):
        uid = player_ref.id
        return users_map.get(uid, {"username": uid, "id": uid})
    return {"username": "Unknown", "id": "unknown"}

def get_doubles_participants(
    match_dict: dict[str, Any], users_map: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Extract participant info for doubles."""
    p1 = [get_player_info(r, users_map) for r in match_dict.get("team1", [])]
    p2 = [get_player_info(r, users_map) for r in match_dict.get("team2", [])]
    return p1, p2

def get_denormalized_participants(match_dict: dict[str, Any]) -> tuple[dict, dict]:
    """Extract participant info from denormalized singles data."""
    p1_snap, p2_snap = match_dict["player_1_data"], match_dict["player_2_data"]
    p1_info = {
        "id": p1_snap.get("uid"),
        "username": p1_snap.get("display_name"),
        "thumbnail_url": p1_snap.get("avatar_url"),
    }
    p2_info = {
        "id": p2_snap.get("uid"),
        "username": p2_snap.get("display_name"),
        "thumbnail_url": p2_snap.get("avatar_url"),
    }
    return p1_info, p2_info

def get_match_participants_info(
    match_dict: dict[str, Any], users_map: dict[str, Any]
) -> tuple[Any, Any]:
    """Extract participant info for singles or doubles."""
    if match_dict.get("matchType") == "doubles":
        return get_doubles_participants(match_dict, users_map)

    if "player_1_data" in match_dict and "player_2_data" in match_dict:
        return get_denormalized_participants(match_dict)

    p1_info = get_player_info(match_dict.get("player1Ref"), users_map)
    p2_info = get_player_info(match_dict.get("player2Ref"), users_map)
    return p1_info, p2_info
