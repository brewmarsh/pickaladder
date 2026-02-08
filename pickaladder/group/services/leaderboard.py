"""Service for group leaderboard and trend calculations."""

from __future__ import annotations

import operator
from datetime import datetime, timedelta, timezone
from typing import Any

from firebase_admin import firestore
from google.cloud.firestore import FieldFilter

from pickaladder.core.constants import (
    HOT_STREAK_THRESHOLD,
    RECENT_MATCHES_LIMIT,
)
from pickaladder.group.services.match_parser import _extract_team_ids, _get_match_scores
from pickaladder.user.helpers import smart_display_name


def _initialize_stats(players: list[Any]) -> dict[str, dict[str, Any]]:
    """Initialize the stats dictionary for each player."""
    return {
        ref.id: {
            "wins": 0,
            "losses": 0,
            "games": 0,
            "total_score": 0,
            "user_data": ref.get(),
            "match_results": [],
        }
        for ref in players
    }


def _process_single_match(stats: dict[str, dict[str, Any]], match: Any) -> None:
    """Update raw stats and records match outcomes for players in a single match."""
    data = match.to_dict()
    p1_score, p2_score = _get_match_scores(data)

    p1_wins = p1_score > p2_score
    p2_wins = p2_score > p1_score
    is_draw = p1_score == p2_score

    def update_player(player_id: str, score: int, won: bool):
        if player_id in stats:
            s = stats[player_id]
            s["games"] += 1
            s["total_score"] += score
            if won:
                s["wins"] += 1
            elif not is_draw:
                s["losses"] += 1
            s["match_results"].append("win" if won else "loss")

    team1_ids, team2_ids = _extract_team_ids(data)
    for uid in team1_ids:
        update_player(uid, p1_score, p1_wins)
    for uid in team2_ids:
        update_player(uid, p2_score, p2_wins)


def _calculate_derived_stats(stats: dict[str, dict[str, Any]]) -> None:
    """Calculate 'Win Rate %', 'Average Score', and 'Form' (last 5 games)."""
    for s in stats.values():
        games = s["games"]
        s["avg_score"] = s["total_score"] / games if games > 0 else 0.0
        s["win_rate"] = (s["wins"] / games * 100) if games > 0 else 0.0
        s["form"] = s["match_results"][:RECENT_MATCHES_LIMIT]


def _sort_leaderboard(stats: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Enrich stats with user data, format into a list, and sort."""
    leaderboard = []
    for user_id, s in stats.items():
        user_doc = s["user_data"]
        if not user_doc.exists:
            continue

        user_data = user_doc.to_dict()
        if user_data is None:
            continue
        user_data["id"] = user_id

        is_ghost = user_data.get("is_ghost") or user_data.get(
            "username", ""
        ).startswith("ghost_")
        entry = {
            "id": user_id,
            "name": smart_display_name(user_data),
            "username": user_data.get("username"),
            "email": user_data.get("email"),
            "is_ghost": is_ghost,
            "wins": s["wins"],
            "losses": s["losses"],
            "games_played": s["games"],
            "avg_score": s["avg_score"],
            "win_rate": s["win_rate"],
            "form": s["form"],
        }
        leaderboard.append(entry)

    leaderboard.sort(
        key=operator.itemgetter("avg_score", "wins", "games_played"), reverse=True
    )
    return leaderboard


def _calculate_leaderboard_from_matches(
    matches: list[Any], players: list[Any]
) -> list[dict[str, Any]]:
    """Calculate the leaderboard from a list of matches using a pipeline of helpers."""
    matches.sort(
        key=lambda m: m.to_dict().get("matchDate") or datetime.min, reverse=True
    )

    stats = _initialize_stats(players)
    for match in matches:
        _process_single_match(stats, match)

    _calculate_derived_stats(stats)
    return _sort_leaderboard(stats)


def _calculate_rank_changes(
    current_leaderboard: list[dict[str, Any]],
    previous_leaderboard: list[dict[str, Any]],
) -> None:
    """Calculate rank changes between current and previous leaderboard."""
    last_week_ranks = {
        player["id"]: i + 1 for i, player in enumerate(previous_leaderboard)
    }

    for i, player in enumerate(current_leaderboard):
        current_rank = i + 1
        last_week_rank = last_week_ranks.get(player["id"])
        if last_week_rank is not None:
            player["rank_change"] = last_week_rank - current_rank
        else:
            player["rank_change"] = "new"


def _map_matches_to_users(
    matches: list[Any], member_refs: list[Any]
) -> dict[str, list[dict[str, Any]]]:
    """Map matches to each user for efficient lookup."""
    user_matches_map: dict[str, list[dict[str, Any]]] = {
        ref.id: [] for ref in member_refs
    }
    for match in matches:
        data = match.to_dict()
        team1_ids, team2_ids = _extract_team_ids(data)
        for uid in team1_ids.union(team2_ids):
            if uid in user_matches_map:
                user_matches_map[uid].append(data)
    return user_matches_map


def _calculate_player_winning_streak(
    user_id: str, matches_data: list[dict[str, Any]]
) -> int:
    """Calculate the current winning streak for a single player."""
    streak = 0
    for data in matches_data:
        p1_score, p2_score = _get_match_scores(data)
        if p1_score == p2_score:
            break

        team1_ids, team2_ids = _extract_team_ids(data)
        won = False
        if user_id in team1_ids:
            won = p1_score > p2_score
        elif user_id in team2_ids:
            won = p2_score > p1_score

        if won:
            streak += 1
        else:
            break
    return streak


def _calculate_winning_streaks(
    leaderboard: list[dict[str, Any]], matches: list[Any], member_refs: list[Any]
) -> None:
    """Calculate winning streaks for players in the leaderboard."""
    user_matches_map = _map_matches_to_users(matches, member_refs)

    for player in leaderboard:
        user_id = player["id"]
        matches_data = user_matches_map.get(user_id, [])
        player["streak"] = _calculate_player_winning_streak(user_id, matches_data)
        player["is_on_fire"] = player["streak"] >= HOT_STREAK_THRESHOLD


def get_group_leaderboard(group_id: str) -> list[dict[str, Any]]:
    """Calculate the leaderboard for a specific group using Firestore."""
    db = firestore.client()
    group_ref = db.collection("groups").document(group_id)
    group = group_ref.get()
    if not group.exists:
        return []

    group_data = group.to_dict()
    member_refs = group_data.get("members", [])
    if not member_refs:
        return []

    all_matches_stream = (
        db.collection("matches")
        .where(filter=FieldFilter("groupId", "==", group_id))
        .stream()
    )
    all_matches = list(all_matches_stream)

    current_leaderboard = _calculate_leaderboard_from_matches(all_matches, member_refs)

    one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    matches_last_week = [
        m
        for m in all_matches
        if m.to_dict().get("matchDate") and m.to_dict().get("matchDate") < one_week_ago
    ]

    last_week_leaderboard = _calculate_leaderboard_from_matches(
        matches_last_week, member_refs
    )

    _calculate_rank_changes(current_leaderboard, last_week_leaderboard)

    all_matches.sort(
        key=lambda m: m.to_dict().get("matchDate") or datetime.min, reverse=True
    )
    _calculate_winning_streaks(current_leaderboard, all_matches, member_refs)

    return current_leaderboard


def _get_involved_player_data(db: Any, matches: list[Any]) -> dict[str, dict[str, Any]]:
    """Get profile data for all players involved in matches."""
    all_player_refs = set()
    for match in matches:
        data = match.to_dict()
        if data.get("matchType", "singles") == "doubles":
            all_player_refs.update(data.get("team1", []))
            all_player_refs.update(data.get("team2", []))
        else:
            if data.get("player1Ref"):
                all_player_refs.add(data.get("player1Ref"))
            if data.get("player2Ref"):
                all_player_refs.add(data.get("player2Ref"))

    player_docs = db.get_all(list(all_player_refs))
    players_data = {}
    for doc in player_docs:
        if doc.exists:
            data = doc.to_dict()
            players_data[doc.id] = {
                "name": data.get("name", "Unknown"),
                "profilePictureUrl": data.get("profilePictureUrl"),
            }
    return players_data


def _calculate_trend_points(
    matches: list[Any], players_data: dict[str, Any], unique_dates: list[str]
) -> dict[str, dict[str, Any]]:
    """Calculate average score trend points for each player."""
    player_stats = {pid: {"total_score": 0, "games": 0} for pid in players_data}
    datasets = {
        pid: {
            "id": pid,
            "label": info["name"],
            "data": [],
            "fill": False,
            "profilePictureUrl": info["profilePictureUrl"],
        }
        for pid, info in players_data.items()
    }

    date_idx = 0
    for i, match in enumerate(matches):
        data = match.to_dict()
        match_date = data.get("matchDate").strftime("%Y-%m-%d")

        while date_idx < len(unique_dates) and unique_dates[date_idx] < match_date:
            for pid in player_stats:
                avg = (
                    player_stats[pid]["total_score"] / player_stats[pid]["games"]
                    if player_stats[pid]["games"] > 0
                    else None
                )
                datasets[pid]["data"].append(avg)
            date_idx += 1

        _update_trend_player_stats(player_stats, data)

        if (
            i == len(matches) - 1
            or matches[i + 1].to_dict().get("matchDate").strftime("%Y-%m-%d")
            != match_date
        ):
            for pid in player_stats:
                avg = (
                    player_stats[pid]["total_score"] / player_stats[pid]["games"]
                    if player_stats[pid]["games"] > 0
                    else None
                )
                datasets[pid]["data"].append(avg)
            date_idx += 1

    return datasets


def _update_trend_player_stats(
    player_stats: dict[str, Any], match_data: dict[str, Any]
):
    """Update running totals for trend calculation from a single match."""
    p1_score, p2_score = _get_match_scores(match_data)
    team1_ids, team2_ids = _extract_team_ids(match_data)

    for uid in team1_ids:
        if uid in player_stats:
            player_stats[uid]["total_score"] += p1_score
            player_stats[uid]["games"] += 1
    for uid in team2_ids:
        if uid in player_stats:
            player_stats[uid]["total_score"] += p2_score
            player_stats[uid]["games"] += 1


def get_leaderboard_trend_data(group_id: str) -> dict[str, Any]:
    """Generate data for a leaderboard trend chart."""
    db = firestore.client()
    matches_query = db.collection("matches").where(
        filter=FieldFilter("groupId", "==", group_id)
    )
    matches = [m for m in matches_query.stream() if m.to_dict().get("matchDate")]
    matches.sort(key=lambda x: x.to_dict().get("matchDate"))
    if not matches:
        return {"labels": [], "datasets": []}

    players_data = _get_involved_player_data(db, matches)
    unique_dates = sorted(
        list({m.to_dict().get("matchDate").strftime("%Y-%m-%d") for m in matches})
    )

    datasets_dict = _calculate_trend_points(matches, players_data, unique_dates)

    for ds in datasets_dict.values():
        while len(ds["data"]) < len(unique_dates):
            ds["data"].append(ds["data"][-1] if ds["data"] else None)

    return {"labels": unique_dates, "datasets": list(datasets_dict.values())}
