"""Utility functions for the group blueprint."""

from __future__ import annotations

import operator
import secrets
import sys
import threading
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from firebase_admin import firestore
from google.cloud.firestore import FieldFilter

# Import internal helpers
from pickaladder.utils import send_email, smart_display_name

if TYPE_CHECKING:
    from flask import Flask

# Constants
FIRESTORE_BATCH_LIMIT = 400
RECENT_MATCHES_LIMIT = 5
HOT_STREAK_THRESHOLD = 3


def get_random_joke() -> str:
    """Return a random sport/dad joke."""
    jokes = [
        "Why did the pickleball player get arrested? Because he was caught smashing!",
        "What do you call a girl standing in the middle of a tennis court? Annette.",
        "Why are fish never good at tennis? Because they don't like getting close to the net.",
        "What is a tennis player's favorite city? Volley-wood.",
        "Why do tennis players never get married? Because love means nothing to them.",
        "What time does a tennis player go to bed? Ten-ish.",
        "Why did the pickleball hit the net? It wanted to see what was on the other side.",
        "How is a pickleball game like a waiter? They both serve.",
        "Why should you never fall in love with a tennis player? To them, 'Love' means nothing.",
        "What do you serve but not eat? A tennis ball.",
    ]
    return secrets.choice(jokes)


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
    """Update raw stats and record outcomes for players in a single match."""
    data = match.to_dict()
    match_type = data.get("matchType", "singles")
    p1_score = data.get("player1Score", 0)
    p2_score = data.get("player2Score", 0)

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

    if match_type == "doubles":
        for ref in data.get("team1", []):
            update_player(ref.id, p1_score, p1_wins)
        for ref in data.get("team2", []):
            update_player(ref.id, p2_score, p2_wins)
    else:
        p1_ref = data.get("player1Ref")
        p2_ref = data.get("player2Ref")
        if p1_ref:
            update_player(p1_ref.id, p1_score, p1_wins)
        if p2_ref:
            update_player(p2_ref.id, p2_score, p2_wins)


def _calculate_derived_stats(stats: dict[str, dict[str, Any]]) -> None:
    """Calculate 'Win Rate %', 'Average Score', and 'Form'."""
    for s in stats.values():
        games = s["games"]
        s["avg_score"] = s["total_score"] / games if games > 0 else 0.0
        s["win_rate"] = (s["wins"] / games * 100) if games > 0 else 0.0
        s["form"] = s["match_results"][:RECENT_MATCHES_LIMIT]


def _sort_leaderboard(stats: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Enrich stats with user data, handle Ghost accounts, and sort."""
    leaderboard = []
    for user_id, s in stats.items():
        user_doc = s["user_data"]
        if not user_doc.exists:
            continue

        user_data = user_doc.to_dict()
        if user_data is None:
            continue
        
        user_data["id"] = user_id

        # Detect Ghost/Placeholder accounts for UI labeling
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
    """Calculate the leaderboard using a processing pipeline."""
    matches.sort(
        key=lambda m: m.to_dict().get("matchDate") or datetime.min, reverse=True
    )

    stats = _initialize_stats(players)
    for match in matches:
        _process_single_match(stats, match)

    _calculate_derived_stats(stats)
    return _sort_leaderboard(stats)


def get_group_leaderboard(group_id: str) -> list[dict[str, Any]]:
    """Primary entry point for group leaderboard calculation."""
    db = firestore.client()
    group_ref = db.collection("groups").document(group_id)
    group = group_ref.get()
    if not group.exists:
        return []

    group_data = group.to_dict()
    member_refs = group_data.get("members", [])
    if not member_refs:
        return []

    all_matches = list(
        db.collection("matches")
        .where(filter=FieldFilter("groupId", "==", group_id))
        .stream()
    )

    current_leaderboard = _calculate_leaderboard_from_matches(all_matches, member_refs)

    # Rank Change Logic
    one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    matches_last_week = [
        m for m in all_matches 
        if m.to_dict().get("matchDate") and m.to_dict().get("matchDate") < one_week_ago
    ]
    last_week_leaderboard = _calculate_leaderboard_from_matches(matches_last_week, member_refs)
    _calculate_rank_changes(current_leaderboard, last_week_leaderboard)

    # Streak Logic
    all_matches.sort(key=lambda m: m.to_dict().get("matchDate") or datetime.min, reverse=True)
    _calculate_winning_streaks(current_leaderboard, all_matches, member_refs)

    return current_leaderboard


def _calculate_rank_changes(current: list[dict], previous: list[dict]) -> None:
    prev_ranks = {p["id"]: i + 1 for i, p in enumerate(previous)}
    for i, player in enumerate(current):
        last_rank = prev_ranks.get(player["id"])
        player["rank_change"] = (last_rank - (i + 1)) if last_rank else "new"


def _calculate_winning_streaks(leaderboard, matches, member_refs) -> None:
    user_map = {ref.id: [] for ref in member_refs}
    for m in matches:
        data = m.to_dict()
        t1, t2 = _extract_team_ids(data)
        for uid in t1.union(t2):
            if uid in user_map: user_map[uid].append(data)

    for p in leaderboard:
        streak = 0
        for m_data in user_map.get(p["id"], []):
            s1, s2 = _get_match_scores(m_data)
            t1, t2 = _extract_team_ids(m_data)
            won = (p["id"] in t1 and s1 > s2) or (p["id"] in t2 and s2 > s1)
            if won: streak += 1
            else: break
        p["streak"] = streak
        p["is_on_fire"] = streak >= HOT_STREAK_THRESHOLD


def _extract_team_ids(data: dict) -> tuple[set, set]:
    t1 = {r.id for r in data.get("team1", [])} if "team1" in data else {data.get("player1Id"), data.get("partnerId")}
    t2 = {r.id for r in data.get("team2", [])} if "team2" in data else {data.get("player2Id"), data.get("opponent2Id")}
    return {i for i in t1 if i}, {i for i in t2 if i}


def _get_match_scores(data: dict) -> tuple[int, int]:
    return data.get("player1Score") or data.get("team1Score", 0), data.get("player2Score") or data.get("team2Score", 0)

# ... [Remaining trend and background email functions preserved from original] ...