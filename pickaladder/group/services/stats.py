"""Service for group head-to-head and partnership statistics."""

from __future__ import annotations

from typing import Any

from firebase_admin import firestore
from google.cloud.firestore import FieldFilter

from pickaladder.group.services.match_parser import _extract_team_ids, _get_match_scores


def get_partnership_stats(
    playerA_id: str, playerB_id: str, all_matches_in_group: list[Any]
) -> dict[str, int]:
    """Calculates the win/loss record for two players when they are partners."""
    wins = 0
    losses = 0

    for match_doc in all_matches_in_group:
        data = match_doc.to_dict()
        if data.get("matchType") != "doubles":
            continue

        team1_ids, team2_ids = _extract_team_ids(data)
        p1_score, p2_score = _get_match_scores(data)

        if {playerA_id, playerB_id}.issubset(team1_ids):
            if p1_score > p2_score:
                wins += 1
            elif p2_score > p1_score:
                losses += 1
        elif {playerA_id, playerB_id}.issubset(team2_ids):
            if p2_score > p1_score:
                wins += 1
            elif p1_score > p2_score:
                losses += 1

    return {"wins": wins, "losses": losses}


def _process_h2h_match(
    match_doc: Any, playerA_id: str, playerB_id: str, stats: dict[str, Any]
) -> None:
    """Process a single match for head-to-head statistics."""
    data = match_doc.to_dict()
    team1_ids, team2_ids = _extract_team_ids(data)

    player_a_is_t1 = playerA_id in team1_ids
    player_b_is_t2 = playerB_id in team2_ids
    player_a_is_t2 = playerA_id in team2_ids
    player_b_is_t1 = playerB_id in team1_ids

    if (player_a_is_t1 and player_b_is_t2) or (player_a_is_t2 and player_b_is_t1):
        match_display_data = data.copy()
        match_display_data["id"] = match_doc.id
        match_display_data["team1_ids"] = list(team1_ids)
        match_display_data["team2_ids"] = list(team2_ids)
        stats["matches"].append(match_display_data)

        p1_score, p2_score = _get_match_scores(data)

        if player_a_is_t1:
            diff, a_pts, b_pts = p1_score - p2_score, p1_score, p2_score
            won = p1_score > p2_score
            lost = p2_score > p1_score
        else:
            diff, a_pts, b_pts = p2_score - p1_score, p2_score, p1_score
            won = p2_score > p1_score
            lost = p1_score > p2_score

        stats["point_diff"] += diff
        stats["playerA_total_points"] += a_pts
        stats["playerB_total_points"] += b_pts
        if won:
            stats["wins"] += 1
        elif lost:
            stats["losses"] += 1


def get_head_to_head_stats(
    group_id: str, playerA_id: str, playerB_id: str
) -> dict[str, Any]:
    """Calculates head-to-head statistics for two players in doubles matches."""
    db = firestore.client()
    query = db.collection("matches").where(
        filter=FieldFilter("groupId", "==", group_id)
    )
    all_matches_in_group = list(query.stream())

    h2h_stats: dict[str, Any] = {
        "wins": 0,
        "losses": 0,
        "point_diff": 0,
        "playerA_total_points": 0,
        "playerB_total_points": 0,
        "matches": [],
    }

    for match_doc in all_matches_in_group:
        _process_h2h_match(match_doc, playerA_id, playerB_id, h2h_stats)

    num_matches = len(h2h_stats["matches"])
    avg_A = h2h_stats["playerA_total_points"] / num_matches if num_matches > 0 else 0
    avg_B = h2h_stats["playerB_total_points"] / num_matches if num_matches > 0 else 0

    return {
        "wins": h2h_stats["wins"],
        "losses": h2h_stats["losses"],
        "matches": h2h_stats["matches"],
        "point_diff": h2h_stats["point_diff"],
        "avg_points_scored": {"playerA": avg_A, "playerB": avg_B},
        "partnership_record": get_partnership_stats(
            playerA_id, playerB_id, all_matches_in_group
        ),
    }


def _calculate_all_time_streaks(matches: list[Any], user_ref: Any) -> tuple[int, int]:
    """Calculate current and longest winning streaks for a user."""
    from datetime import datetime

    matches.sort(key=lambda x: x.to_dict().get("matchDate") or datetime.min)
    current = longest = 0

    for match in matches:
        data = match.to_dict()
        p1_score, p2_score = _get_match_scores(data)
        team1_ids, team2_ids = _extract_team_ids(data)

        user_participated = False
        user_won = False

        if user_ref.id in team1_ids:
            user_participated = True
            user_won = p1_score > p2_score
        elif user_ref.id in team2_ids:
            user_participated = True
            user_won = p2_score > p1_score

        if user_participated:
            if user_won:
                current += 1
            else:
                longest = max(longest, current)
                current = 0

    return current, max(longest, current)


def get_user_group_stats(group_id: str, user_id: str) -> dict[str, Any]:
    """Calculate detailed statistics for a specific user within a group."""
    from pickaladder.group.services.leaderboard import get_group_leaderboard

    db = firestore.client()
    leaderboard = get_group_leaderboard(group_id)
    user_data = next((p for p in leaderboard if p["id"] == user_id), None)

    stats = {
        "rank": "N/A",
        "wins": 0,
        "losses": 0,
        "win_streak": 0,
        "longest_streak": 0,
    }

    if user_data:
        stats["rank"] = leaderboard.index(user_data) + 1
        stats["wins"] = user_data.get("wins", 0)
        stats["losses"] = user_data.get("losses", 0)

    matches_query = db.collection("matches").where(
        filter=FieldFilter("groupId", "==", group_id)
    )
    all_matches = list(matches_query.stream())
    user_ref = db.collection("users").document(user_id)

    curr, long = _calculate_all_time_streaks(all_matches, user_ref)
    stats["win_streak"] = curr
    stats["longest_streak"] = long

    return stats
