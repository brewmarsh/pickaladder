from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client


def _get_player_info(player_ref: Any, users_map: dict[str, Any]) -> dict[str, Any]:
    """Extract player info from a reference or dictionary."""
    if hasattr(player_ref, "id"):
        uid = player_ref.id
        return users_map.get(uid, {"username": uid, "id": uid})
    return {"username": "Unknown", "id": "unknown"}


def _format_match_date(match_date: Any) -> str:
    """Format match date to string."""
    if isinstance(match_date, datetime.datetime):
        return match_date.strftime("%b %d")
    return str(match_date) if match_date else "N/A"


def _get_match_participants_info(
    match_dict: dict[str, Any], users_map: dict[str, Any]
) -> tuple[
    dict[str, Any] | list[dict[str, Any]], dict[str, Any] | list[dict[str, Any]]
]:
    """Extract participant info for singles or doubles."""
    p1_info: dict[str, Any] | list[dict[str, Any]]
    p2_info: dict[str, Any] | list[dict[str, Any]]

    if match_dict.get("matchType") == "doubles":
        p1_info = [_get_player_info(r, users_map) for r in match_dict.get("team1", [])]
        p2_info = [_get_player_info(r, users_map) for r in match_dict.get("team2", [])]
    elif "player_1_data" in match_dict and "player_2_data" in match_dict:
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
    else:
        p1_info = _get_player_info(match_dict.get("player1Ref"), users_map)
        p2_info = _get_player_info(match_dict.get("player2Ref"), users_map)
    return p1_info, p2_info


def _resolve_team_names(
    match_dict: dict[str, Any], teams_map: dict[str, Any]
) -> tuple[str, str]:
    """Resolve team names from team references and the teams map."""
    t1_name = "Team 1"
    t2_name = "Team 2"
    if t1_ref := match_dict.get("team1Ref"):
        t1_name = teams_map.get(t1_ref.id, {}).get("name", "Team 1")
    if t2_ref := match_dict.get("team2Ref"):
        t2_name = teams_map.get(t2_ref.id, {}).get("name", "Team 2")
    return t1_name, t2_name


def _build_match_dashboard_item(
    match_doc: DocumentSnapshot,
    m_data: dict[str, Any],
    user_id: str,
    entity_maps: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Build a single match data item for the dashboard."""
    from .match_stats import _get_match_winner_slot, _get_user_match_result

    winner = _get_match_winner_slot(m_data)
    user_result = _get_user_match_result(m_data, user_id, winner)
    p1_info, p2_info = _get_match_participants_info(m_data, entity_maps["users"])
    t1_name, t2_name = _resolve_team_names(m_data, entity_maps["teams"])

    t_id = m_data.get("tournamentId")
    tournament_name = (
        entity_maps["tournaments"].get(t_id, {}).get("name") if t_id else None
    )

    return {
        "id": match_doc.id,
        "player1": p1_info,
        "player2": p2_info,
        "player1_score": m_data.get("player1Score", 0),
        "player2_score": m_data.get("player2Score", 0),
        "winner": winner,
        "date": _format_match_date(m_data.get("matchDate")),
        "is_group_match": bool(m_data.get("groupId")),
        "match_type": m_data.get("matchType", "singles"),
        "user_result": user_result,
        "team1_name": t1_name,
        "team2_name": t2_name,
        "tournament_name": tournament_name,
        "created_by": m_data.get("createdBy"),
        "tournament_id": t_id,
        "player_1_data": m_data.get("player_1_data"),
        "player_2_data": m_data.get("player_2_data"),
    }


def _extract_refs_from_match(
    m_data: dict[str, Any],
    user_refs: set[Any],
    team_refs: set[Any],
    tournament_ids: set[str],
) -> None:
    """Collect unique user, team, and tournament references from a single match."""
    if m_data.get("matchType") == "doubles":
        user_refs.update(m_data.get("team1", []))
        user_refs.update(m_data.get("team2", []))
    else:
        if p1 := m_data.get("player1Ref"):
            user_refs.add(p1)
        if p2 := m_data.get("player2Ref"):
            user_refs.add(p2)

    if t1 := m_data.get("team1Ref"):
        team_refs.add(t1)
    if t2 := m_data.get("team2Ref"):
        team_refs.add(t2)

    if t_id := m_data.get("tournamentId"):
        tournament_ids.add(t_id)


def _collect_match_refs(
    matches: list[DocumentSnapshot],
) -> tuple[set[Any], set[Any], set[str]]:
    """Collect all unique user, team, and tournament references from matches."""
    user_refs: set[Any] = set()
    team_refs: set[Any] = set()
    tournament_ids: set[str] = set()

    for match_doc in matches:
        if m_data := match_doc.to_dict():
            _extract_refs_from_match(m_data, user_refs, team_refs, tournament_ids)

    return user_refs, team_refs, tournament_ids


def _get_users_map(db: Client, user_refs: set[Any]) -> dict[str, Any]:
    """Batch fetch users and return a map."""
    users_map: dict[str, Any] = {}
    if not user_refs:
        return users_map
    for doc in db.get_all(list(user_refs)):
        if doc.exists and (d := doc.to_dict()):
            d["id"] = doc.id
            users_map[doc.id] = d
    return users_map


def _get_teams_map(db: Client, team_refs: set[Any]) -> dict[str, Any]:
    """Batch fetch teams and return a map."""
    teams_map: dict[str, Any] = {}
    if not team_refs:
        return teams_map
    for doc in db.get_all(list(team_refs)):
        if doc.exists and (d := doc.to_dict()):
            d["id"] = doc.id
            teams_map[doc.id] = d
    return teams_map


def _get_tournaments_map(db: Client, tournament_ids: set[str]) -> dict[str, Any]:
    """Batch fetch tournaments and return a map."""
    tournaments_map: dict[str, Any] = {}
    if not tournament_ids:
        return tournaments_map
    t_refs = [db.collection("tournaments").document(tid) for tid in tournament_ids]
    for doc in db.get_all(t_refs):
        if doc.exists and (d := doc.to_dict()):
            d["id"] = doc.id
            tournaments_map[doc.id] = d
    return tournaments_map


def _fetch_match_entities(
    db: Client, user_refs: set[Any], team_refs: set[Any], tournament_ids: set[str]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Batch fetch users, teams, and tournaments from Firestore."""
    return (
        _get_users_map(db, user_refs),
        _get_teams_map(db, team_refs),
        _get_tournaments_map(db, tournament_ids),
    )


def _prepare_entity_maps(
    db: Client, matches: list[DocumentSnapshot]
) -> dict[str, dict[str, Any]]:
    """Prepare entity maps for users, teams, and tournaments from matches."""
    user_refs, team_refs, tournament_ids = _collect_match_refs(matches)
    users_map, teams_map, tournaments_map = _fetch_match_entities(
        db, user_refs, team_refs, tournament_ids
    )
    return {
        "users": users_map,
        "teams": teams_map,
        "tournaments": tournaments_map,
    }


def _build_dashboard_match_list(
    matches: list[DocumentSnapshot],
    user_id: str,
    entity_maps: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build a list of dashboard match data items."""
    matches_data = []
    for match_doc in matches:
        if m_data := match_doc.to_dict():
            matches_data.append(
                _build_match_dashboard_item(match_doc, m_data, user_id, entity_maps)
            )
    return matches_data


def format_matches_for_dashboard(
    db: Client, matches: list[DocumentSnapshot], user_id: str
) -> list[dict[str, Any]]:
    """Format match documents for the dashboard UI."""
    if not matches:
        return []

    entity_maps = _prepare_entity_maps(db, matches)
    return _build_dashboard_match_list(matches, user_id, entity_maps)


def format_matches_for_profile(
    db: Client, matches: list[DocumentSnapshot], user_id: str
) -> list[dict[str, Any]]:
    """Format matches for profile using dashboard formatter as fallback."""
    return format_matches_for_dashboard(db, matches, user_id)
