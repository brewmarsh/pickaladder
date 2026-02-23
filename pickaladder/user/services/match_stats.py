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


def _get_player_info(player_ref: Any, users_map: dict[str, Any]) -> dict[str, Any]:
    """Extract player info from a reference or dictionary."""
    if hasattr(player_ref, "id"):
        uid = player_ref.id
        return users_map.get(uid, {"username": uid, "id": uid})
    return {"username": "Unknown", "id": "unknown"}


def _get_user_match_result(
    match_dict: dict[str, Any], user_id: str, winner_slot: str
) -> str:
    """Determine if the user won or lost the match."""
    match_type = match_dict.get("matchType", "singles")
    if match_type == "doubles":
        team1_refs = match_dict.get("team1", [])
        is_in_team1 = any(ref.id == user_id for ref in team1_refs)
        if (is_in_team1 and winner_slot == "team1") or (
            not is_in_team1 and winner_slot == "team2"
        ):
            return "win"
        return "loss"
    else:
        p1_ref = match_dict.get("player1Ref")
        is_player1 = p1_ref and p1_ref.id == user_id
        if (is_player1 and winner_slot == "team1") or (
            not is_player1 and winner_slot == "team2"
        ):
            return "win"
        return "loss"


def _get_match_winner_slot(match_dict: dict[str, Any]) -> str:
    """Determine the winner slot ('team1' or 'team2')."""
    p1_score = match_dict.get("player1Score", 0)
    p2_score = match_dict.get("player2Score", 0)
    return "team1" if p1_score > p2_score else "team2"


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


def _fetch_users(db: Client, user_refs: set[Any], users_map: dict[str, Any]) -> None:
    """Batch fetch users from Firestore."""
    if not user_refs:
        return
    for doc in db.get_all(list(user_refs)):
        if doc.exists and (d := doc.to_dict()):
            d["id"] = doc.id
            users_map[doc.id] = d


def _fetch_teams(db: Client, team_refs: set[Any], teams_map: dict[str, Any]) -> None:
    """Batch fetch teams from Firestore."""
    if not team_refs:
        return
    for doc in db.get_all(list(team_refs)):
        if doc.exists and (d := doc.to_dict()):
            d["id"] = doc.id
            teams_map[doc.id] = d


def _fetch_tournaments(
    db: Client, tournament_ids: set[str], tournaments_map: dict[str, Any]
) -> None:
    """Batch fetch tournaments from Firestore."""
    if not tournament_ids:
        return
    t_refs = [db.collection("tournaments").document(tid) for tid in tournament_ids]
    for doc in db.get_all(t_refs):
        if doc.exists and (d := doc.to_dict()):
            d["id"] = doc.id
            tournaments_map[doc.id] = d


def _fetch_match_entities(
    db: Client, user_refs: set[Any], team_refs: set[Any], tournament_ids: set[str]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Batch fetch users, teams, and tournaments from Firestore."""
    users_map: dict[str, Any] = {}
    teams_map: dict[str, Any] = {}
    tournaments_map: dict[str, Any] = {}

    _fetch_users(db, user_refs, users_map)
    _fetch_teams(db, team_refs, teams_map)
    _fetch_tournaments(db, tournament_ids, tournaments_map)

    return users_map, teams_map, tournaments_map


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


def format_matches_for_dashboard(
    db: Client, matches: list[DocumentSnapshot], user_id: str
) -> list[dict[str, Any]]:
    """Format match documents for the dashboard UI."""
    if not matches:
        return []

    user_refs, team_refs, tournament_ids = _collect_match_refs(matches)
    users_map, teams_map, tournaments_map = _fetch_match_entities(
        db, user_refs, team_refs, tournament_ids
    )

    entity_maps = {
        "users": users_map,
        "teams": teams_map,
        "tournaments": tournaments_map,
    }
    matches_data = []
    for match_doc in matches:
        if m_data := match_doc.to_dict():
            matches_data.append(
                _build_match_dashboard_item(match_doc, m_data, user_id, entity_maps)
            )
    return matches_data


def _get_user_match_won_lost(
    match_data: dict[str, Any], user_id: str
) -> tuple[bool, bool]:
    """Determine if the user won or lost the match, including handling of draws."""
    match_type = match_data.get("matchType", "singles")
    p1_score = match_data.get("player1Score", 0)
    p2_score = match_data.get("player2Score", 0)

    if match_type == "doubles":
        team1_refs = match_data.get("team1", [])
        in_team1 = any(ref.id == user_id for ref in team1_refs)
        if in_team1:
            return (p1_score > p2_score), (p1_score <= p2_score)
        return (p2_score > p1_score), (p2_score <= p1_score)
    else:
        p1_ref = match_data.get("player1Ref")
        is_player1 = p1_ref and p1_ref.id == user_id
        if is_player1:
            return (p1_score > p2_score), (p1_score <= p2_score)
        return (p2_score > p1_score), (p2_score <= p1_score)


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
        key=lambda x: x["date"] if x["date"] else datetime.datetime.min, reverse=True
    )

    streak = 0
    for m in processed:
        if m["won"]:
            streak += 1
        elif m["lost"]:
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


def _extract_opponent_ids(user_id: str, matches: list[Any], limit: int) -> list[str]:
    """Extract unique 1v1 opponent IDs from matches."""
    opponent_ids: list[str] = []
    for m in matches:
        data = m.to_dict() if hasattr(m, "to_dict") else m
        if opp_id := _get_opponent_id_from_match(data, user_id):
            if opp_id not in opponent_ids:
                opponent_ids.append(opp_id)
                if len(opponent_ids) >= limit:
                    break
    return opponent_ids


def get_recent_opponents(
    db: Client, user_id: str, matches: list[Any], limit: int = 4
) -> list[User]:
    """Identify recent unique 1v1 opponents."""
    opponent_ids = _extract_opponent_ids(user_id, matches, limit)
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


def _process_h2h_match(
    data: dict[str, Any], user_id_1: str, user_id_2: str
) -> tuple[int, int, int]:
    """Process a single match for H2H stats and return (wins, losses, points)."""
    p1_score, p2_score = (
        int(data.get("player1Score", 0)),
        int(data.get("player2Score", 0)),
    )
    if p1_score == p2_score:
        return 0, 0, 0

    t1_ids, t2_ids = _get_team_ids_from_match(data)
    if user_id_1 in t1_ids and user_id_2 in t2_ids:
        return (
            (1 if p1_score > p2_score else 0),
            (1 if p1_score < p2_score else 0),
            (p1_score - p2_score),
        )
    if user_id_1 in t2_ids and user_id_2 in t1_ids:
        return (
            (1 if p2_score > p1_score else 0),
            (1 if p2_score < p1_score else 0),
            (p2_score - p1_score),
        )
    return 0, 0, 0


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
                w, l_count, p_diff = _process_h2h_match(data, user_id_1, user_id_2)
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


def format_matches_for_profile(
    db: Client, matches: list[DocumentSnapshot], user_id: str
) -> list[dict[str, Any]]:
    """Format matches for profile using dashboard formatter as fallback."""
    return format_matches_for_dashboard(db, matches, user_id)
