from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, cast

from firebase_admin import firestore

from .core import smart_display_name

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client

    from ..models import User


def get_user_matches(db: Client, user_id: str) -> list[DocumentSnapshot]:
    """Fetch all matches involving a user."""
    user_ref = db.collection("users").document(user_id)
    matches_as_p1 = (
        db.collection("matches")
        .where(filter=firestore.FieldFilter("player1Ref", "==", user_ref))
        .stream()
    )
    matches_as_p2 = (
        db.collection("matches")
        .where(filter=firestore.FieldFilter("player2Ref", "==", user_ref))
        .stream()
    )
    matches_as_t1 = (
        db.collection("matches")
        .where(filter=firestore.FieldFilter("team1", "array_contains", user_ref))
        .stream()
    )
    matches_as_t2 = (
        db.collection("matches")
        .where(filter=firestore.FieldFilter("team2", "array_contains", user_ref))
        .stream()
    )

    all_matches = (
        list(matches_as_p1)
        + list(matches_as_p2)
        + list(matches_as_t1)
        + list(matches_as_t2)
    )
    unique_matches = {match.id: match for match in all_matches}.values()
    return sorted(
        unique_matches,
        key=lambda m: ((m.to_dict() or {}).get("matchDate") or m.create_time),
        reverse=True,
    )


def _get_player_info(player_ref: Any, users_map: dict[str, Any]) -> dict[str, Any]:
    """Return a dictionary with player info."""
    player_data = users_map.get(player_ref.id)
    if not player_data:
        return {"id": player_ref.id, "username": "Unknown", "thumbnail_url": ""}
    return {
        "id": player_ref.id,
        "username": smart_display_name(player_data),
        "thumbnail_url": player_data.get("thumbnail_url", ""),
    }


def _get_match_winner_slot(match_data: dict[str, Any]) -> str:
    """Determine the winner slot of a match."""
    p1_score = match_data.get("player1Score", 0)
    p2_score = match_data.get("player2Score", 0)
    return "player1" if p1_score > p2_score else "player2"


def _get_user_match_result(
    match_data: dict[str, Any], user_id: str, winner: str
) -> str:
    """Determine if the user won, lost, or drew the match."""
    p1_score = match_data.get("player1Score", 0)
    p2_score = match_data.get("player2Score", 0)

    if p1_score == p2_score:
        return "draw"

    user_won = False
    if match_data.get("matchType") == "doubles":
        team1_refs = match_data.get("team1", [])
        in_team1 = any(ref.id == user_id for ref in team1_refs)
        if (in_team1 and winner == "player1") or (not in_team1 and winner == "player2"):
            user_won = True
    else:
        p1_ref = match_data.get("player1Ref")
        is_player1 = p1_ref and p1_ref.id == user_id
        if (is_player1 and winner == "player1") or (
            not is_player1 and winner == "player2"
        ):
            user_won = True

    return "win" if user_won else "loss"


def _collect_match_refs(
    matches_docs: list[DocumentSnapshot],
) -> tuple[set[Any], set[Any]]:
    """Collect all unique user and team references from match documents."""
    player_refs = set()
    team_refs = set()
    for match_doc in matches_docs:
        match = match_doc.to_dict()
        if match is None:
            continue
        if match.get("player1Ref"):
            player_refs.add(match["player1Ref"])
        if match.get("player2Ref"):
            player_refs.add(match["player2Ref"])
        player_refs.update(match.get("team1", []))
        player_refs.update(match.get("team2", []))
        if match.get("team1Ref"):
            team_refs.add(match["team1Ref"])
        if match.get("team2Ref"):
            team_refs.add(match["team2Ref"])
    return player_refs, team_refs


def _fetch_match_entities(
    db: Client, matches_docs: list[DocumentSnapshot]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Fetch all users and teams involved in a list of matches."""
    player_refs, team_refs = _collect_match_refs(matches_docs)

    users_map = {}
    if player_refs:
        user_docs = db.get_all(list(player_refs))
        users_map = {doc.id: doc.to_dict() for doc in user_docs if doc.exists}

    teams_map = {}
    if team_refs:
        team_docs = db.get_all(list(team_refs))
        teams_map = {doc.id: doc.to_dict() for doc in team_docs if doc.exists}

    return users_map, teams_map


def _get_profile_match_alignment(
    data: dict[str, Any],
    user_id: str,
    profile_username: str,
    users_map: dict[str, Any],
) -> dict[str, Any]:
    """Align match data so the profile user is in the expected slot for UI."""
    match_type = data.get("matchType", "singles")
    p1_info = {"username": "Unknown"}
    p2_info = {"id": "", "username": "Unknown"}
    p1_id = ""

    if match_type == "doubles":
        team1_refs = data.get("team1", [])
        team2_refs = data.get("team2", [])
        in_team1 = any(ref.id == user_id for ref in team1_refs)
        opp_refs = team2_refs if in_team1 else team1_refs

        opp_name = "Unknown Team"
        opp_id = ""
        if opp_refs:
            opp_ref = opp_refs[0]
            opp_id = opp_ref.id
            opp_name = users_map.get(opp_id, {}).get("username", "Unknown")
            if len(team1_refs) > 1 or len(team2_refs) > 1:
                opp_name += " (Doubles)"

        if in_team1:
            p1_id, p1_info = user_id, {"id": user_id, "username": profile_username}
            p2_info = {"id": opp_id, "username": opp_name}
        else:
            p1_info = {"id": opp_id, "username": opp_name}
            p2_info = {"id": user_id, "username": profile_username}
    else:
        p1_ref = data.get("player1Ref")
        p2_ref = data.get("player2Ref")
        if p1_ref and p1_ref.id == user_id:
            p1_id, p1_info = user_id, {"id": user_id, "username": profile_username}
            opp_ref = p2_ref
            p2_info = {
                "id": opp_ref.id if opp_ref else "",
                "username": users_map.get(opp_ref.id, {}).get("username", "Unknown")
                if opp_ref
                else "Unknown",
            }
        else:
            p1_id = p1_ref.id if p1_ref else ""
            p1_info = {
                "id": p1_id,
                "username": users_map.get(p1_id, {}).get("username", "Unknown")
                if p1_id
                else "Unknown",
            }
            p2_info = {"id": user_id, "username": profile_username}

    return {"player1_id": p1_id, "player1": p1_info, "player2": p2_info}


def format_matches_for_profile(
    db: Client,
    display_items: list[dict[str, Any]],
    user_id: str,
    profile_user_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Format matches for the public profile view with consistent alignment."""
    matches_docs = [item["doc"] for item in display_items]
    users_map, _ = _fetch_match_entities(db, matches_docs)
    profile_username = profile_user_data.get("username", "Unknown")
    final_matches = []

    for item in display_items:
        data = item["data"]
        alignment = _get_profile_match_alignment(
            data, user_id, profile_username, users_map
        )

        final_matches.append(
            {
                "id": item["doc"].id,
                "match_date": data.get("matchDate"),
                "player1_score": data.get("player1Score", 0),
                "player2_score": data.get("player2Score", 0),
                **alignment,
            }
        )
    return final_matches


def format_matches_for_dashboard(
    db: Client, matches_docs: list[DocumentSnapshot], user_id: str
) -> list[dict[str, Any]]:
    """Enrich match documents with user and team data for dashboard display."""
    users_map, teams_map = _fetch_match_entities(db, matches_docs)

    # Batch fetch tournament names
    tournament_ids = set()
    for m in matches_docs:
        m_data = m.to_dict()
        if m_data and (tid := m_data.get("tournamentId")):
            tournament_ids.add(tid)
    tournaments_map: dict[str, dict[str, Any]] = {}
    if tournament_ids:
        tournament_refs = [
            db.collection("tournaments").document(tid) for tid in tournament_ids if tid
        ]
        tournament_docs = db.get_all(tournament_refs)
        for doc in tournament_docs:
            if doc.exists and (d := doc.to_dict()):
                tournaments_map[doc.id] = d

    matches_data = []

    for match_doc in matches_docs:
        m_data = match_doc.to_dict()
        if m_data is None:
            continue
        match_dict: dict[str, Any] = m_data

        winner = _get_match_winner_slot(match_dict)
        user_result = _get_user_match_result(match_dict, user_id, winner)

        p1_info: dict[str, Any] | list[dict[str, Any]]
        p2_info: dict[str, Any] | list[dict[str, Any]]

        if match_dict.get("matchType") == "doubles":
            p1_info = [
                _get_player_info(r, users_map) for r in match_dict.get("team1", [])
            ]
            p2_info = [
                _get_player_info(r, users_map) for r in match_dict.get("team2", [])
            ]
        else:
            p1_info = _get_player_info(match_dict["player1Ref"], users_map)
            p2_info = _get_player_info(match_dict["player2Ref"], users_map)

        t1_name = "Team 1"
        t2_name = "Team 2"
        if t1_ref := match_dict.get("team1Ref"):
            t1_name = teams_map.get(t1_ref.id, {}).get("name", "Team 1")
        if t2_ref := match_dict.get("team2Ref"):
            t2_name = teams_map.get(t2_ref.id, {}).get("name", "Team 2")

        tournament_name = None
        if t_id := match_dict.get("tournamentId"):
            tournament_name = tournaments_map.get(t_id, {}).get("name")

        matches_data.append(
            {
                "id": match_doc.id,
                "player1": p1_info,
                "player2": p2_info,
                "player1_score": m_data.get("player1Score", 0),
                "player2_score": m_data.get("player2Score", 0),
                "winner": winner,
                "date": m_data.get("matchDate", "N/A"),
                "match_date": m_data.get("matchDate"),
                "is_group_match": bool(m_data.get("groupId")),
                "match_type": m_data.get("matchType", "singles"),
                "user_result": user_result,
                "team1_name": t1_name,
                "team2_name": t2_name,
                "tournament_name": tournament_name,
            }
        )
    return matches_data


def _get_user_match_won_lost(
    match_data: dict[str, Any], user_id: str
) -> tuple[bool, bool]:
    """Determine if the user won or lost the match, including handling of draws."""
    match_type = match_data.get("matchType", "singles")
    p1_score = match_data.get("player1Score", 0)
    p2_score = match_data.get("player2Score", 0)

    user_won = False
    user_lost = False

    if match_type == "doubles":
        team1_refs = match_data.get("team1", [])
        in_team1 = any(ref.id == user_id for ref in team1_refs)
        if in_team1:
            user_won, user_lost = (p1_score > p2_score), (p1_score <= p2_score)
        else:
            user_won, user_lost = (p2_score > p1_score), (p2_score <= p1_score)
    else:
        p1_ref = match_data.get("player1Ref")
        is_player1 = p1_ref and p1_ref.id == user_id
        if is_player1:
            user_won, user_lost = (p1_score > p2_score), (p1_score <= p2_score)
        else:
            user_won, user_lost = (p2_score > p1_score), (p2_score <= p1_score)

    return user_won, user_lost


def calculate_current_streak(user_id: str, matches: list[Any]) -> int:
    """Calculate current win streak for a user."""
    processed = []
    for m in matches:
        if hasattr(m, "to_dict"):
            data = m.to_dict()
            date = data.get("matchDate") if data else None
            if date is None:
                date = getattr(m, "create_time", None)
        else:
            data = m
            date = data.get("matchDate") or data.get("date")

        if not data:
            continue

        won, lost = _get_user_match_won_lost(data, user_id)
        processed.append({"won": won, "lost": lost, "date": date})

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


def get_recent_opponents(
    db: Client, user_id: str, matches: list[Any], limit: int = 4
) -> list[User]:
    """Identify recent unique 1v1 opponents."""
    opponent_ids: list[str] = []
    for m in matches:
        if hasattr(m, "to_dict"):
            data = m.to_dict()
        else:
            data = m

        if not data or data.get("matchType") == "doubles":
            continue

        p1_ref = data.get("player1Ref")
        p2_ref = data.get("player2Ref")

        opp_id = None
        if p1_ref and p1_ref.id == user_id:
            if p2_ref:
                opp_id = p2_ref.id
        elif p2_ref and p2_ref.id == user_id:
            if p1_ref:
                opp_id = p1_ref.id

        if opp_id and opp_id not in opponent_ids:
            opponent_ids.append(opp_id)
            if len(opponent_ids) >= limit:
                break

    if not opponent_ids:
        return []

    refs = [db.collection("users").document(oid) for oid in opponent_ids]
    docs = db.get_all(refs)
    opponents_map = {}
    for doc in docs:
        if doc.exists:
            d = doc.to_dict()
            if d:
                d["id"] = doc.id
                d["uid"] = doc.id
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
        match_data = match_doc.to_dict()
        if not match_data:
            continue

        won, lost = _get_user_match_won_lost(match_data, user_id)
        if won:
            wins += 1
        elif lost:
            losses += 1

        processed.append(
            {
                "doc": match_doc,
                "data": match_data,
                "date": match_data.get("matchDate") or match_doc.create_time,
                "user_won": won,
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


def _process_h2h_match(
    data: dict[str, Any], user_id_1: str, user_id_2: str
) -> tuple[int, int, int]:
    """Process a single match for H2H stats and return (wins, losses, points)."""
    wins = losses = points = 0
    match_type = data.get("matchType", "singles")

    if match_type == "singles":
        is_p1 = data.get("player1Id") == user_id_1
        winner_id = data.get("winnerId")
        if winner_id == user_id_1:
            wins += 1
        elif winner_id == user_id_2:
            losses += 1

        p1_score = data.get("player1Score", 0)
        p2_score = data.get("player2Score", 0)
        points += (p1_score - p2_score) if is_p1 else (p2_score - p1_score)
    else:
        team1_ids = data.get("team1Id", [])
        team2_ids = data.get("team2Id", [])
        winner_id = data.get("winnerId")

        if user_id_1 in team1_ids and user_id_2 in team2_ids:
            if winner_id == "team1":
                wins += 1
            else:
                losses += 1
            points += data.get("player1Score", 0) - data.get("player2Score", 0)
        elif user_id_1 in team2_ids and user_id_2 in team1_ids:
            if winner_id == "team2":
                wins += 1
            else:
                losses += 1
            points += data.get("player2Score", 0) - data.get("player1Score", 0)

    return wins, losses, points


def get_h2h_stats(db: Client, user_id_1: str, user_id_2: str) -> dict[str, Any] | None:
    """Fetch head-to-head statistics between two users."""
    wins = losses = points = 0

    # Build queries
    matches_ref = db.collection("matches")

    q1 = (
        matches_ref.where("player1Id", "==", user_id_1)
        .where("player2Id", "==", user_id_2)
        .where("status", "==", "completed")
    )
    q2 = (
        matches_ref.where("player1Id", "==", user_id_2)
        .where("player2Id", "==", user_id_1)
        .where("status", "==", "completed")
    )
    q3 = (
        matches_ref.where("participants", "array_contains", user_id_1)
        .where("matchType", "==", "doubles")
        .where("status", "==", "completed")
    )

    for q_obj in [q1, q2, q3]:
        for match in q_obj.stream():
            data = match.to_dict()
            if data:
                w, l_count, p_diff = _process_h2h_match(data, user_id_1, user_id_2)
                wins += w
                losses += l_count
                points += p_diff

    if wins > 0 or losses > 0:
        return {"wins": wins, "losses": losses, "point_diff": points}
    return None
