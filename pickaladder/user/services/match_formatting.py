from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client


def _format_match_date(match_date: Any) -> str:
    """Format match date to string."""
    if isinstance(match_date, datetime.datetime):
        return match_date.strftime("%b %d")
    return str(match_date) if match_date else "N/A"


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


def _get_match_tournament_info(
    m_data: dict[str, Any], entity_maps: dict[str, dict[str, Any]]
) -> tuple[str | None, str | None]:
    """Extract tournament ID and name from match data and maps."""
    tid = m_data.get("tournamentId")
    t_name = entity_maps["tournaments"].get(tid, {}).get("name") if tid else None
    return tid, t_name


def _build_match_dashboard_item(
    match_doc: DocumentSnapshot,
    m_data: dict[str, Any],
    user_id: str,
    entity_maps: dict[str, dict[str, Any]],
) -> Any:
    """Build a single match data item for the dashboard."""
    from pickaladder.match.models import Match

    from .match_participant_service import get_match_participants_info
    from .stats_utils import _get_match_winner_slot, _get_user_match_result

    win_slot = _get_match_winner_slot(m_data)
    p1, p2 = get_match_participants_info(m_data, entity_maps["users"])
    t1_name, t2_name = _resolve_team_names(m_data, entity_maps["teams"])
    tid, t_name = _get_match_tournament_info(m_data, entity_maps)

    return Match(
        {
            "id": match_doc.id,
            "player1": p1,
            "player2": p2,
            "player1_score": m_data.get("player1Score", 0),
            "player2_score": m_data.get("player2Score", 0),
            "winner": win_slot,
            "date": _format_match_date(m_data.get("matchDate")),
            "is_group_match": bool(m_data.get("groupId")),
            "match_type": m_data.get("matchType", "singles"),
            "user_result": _get_user_match_result(m_data, user_id, win_slot),
            "team1_name": t1_name,
            "team2_name": t2_name,
            "tournament_name": t_name,
            "created_by": m_data.get("createdBy"),
            "tournament_id": tid,
            "player_1_data": m_data.get("player_1_data"),
            "player_2_data": m_data.get("player_2_data"),
        }
    )


def _extract_user_refs(m_data: dict[str, Any], user_refs: set[Any]) -> None:
    """Extract user references from match data."""
    if m_data.get("matchType") == "doubles":
        user_refs.update(m_data.get("team1", []))
        user_refs.update(m_data.get("team2", []))
    else:
        if p1 := m_data.get("player1Ref"):
            user_refs.add(p1)
        if p2 := m_data.get("player2Ref"):
            user_refs.add(p2)


def _extract_refs_from_match(
    m_data: dict[str, Any],
    user_refs: set[Any],
    team_refs: set[Any],
    tournament_ids: set[str],
) -> None:
    """Collect unique user, team, and tournament references from a single match."""
    _extract_user_refs(m_data, user_refs)

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


def _prepare_entity_maps(
    db: Client, matches: list[DocumentSnapshot]
) -> dict[str, dict[str, Any]]:
    """Prepare entity maps for users, teams, and tournaments from matches."""
    from .match_entity_service import fetch_match_entities

    user_refs, team_refs, tournament_ids = _collect_match_refs(matches)
    u_map, t_map, tr_map = fetch_match_entities(
        db, user_refs, team_refs, tournament_ids
    )
    return {
        "users": u_map,
        "teams": t_map,
        "tournaments": tr_map,
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
