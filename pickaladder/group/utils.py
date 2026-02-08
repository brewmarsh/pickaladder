"""Utility functions for the group blueprint."""

from __future__ import annotations

import operator
import secrets
import sys
import threading
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from firebase_admin import firestore

if TYPE_CHECKING:
    from flask import Flask
from google.cloud.firestore import FieldFilter

from pickaladder.core.constants import (
    FIRESTORE_BATCH_LIMIT,
    HOT_STREAK_THRESHOLD,
    RECENT_MATCHES_LIMIT,
)
from pickaladder.user.helpers import smart_display_name
from pickaladder.utils import send_email

# Resolved: Import the extracted match parsing logic
from .services.match_parser import _extract_team_ids, _get_match_scores


def get_random_joke() -> str:
    """Return a random sport/dad joke."""
    jokes = [
        "Why did the pickleball player get arrested? Because he was caught smashing!",
        "What do you call a girl standing in the middle of a tennis court? Annette.",
        (
            "Why are fish never good at tennis? Because they don't like getting "
            "close to the net."
        ),
        "What is a tennis player's favorite city? Volley-wood.",
        "Why do tennis players never get married? Because love means nothing to them.",
        "What time does a tennis player go to bed? Ten-ish.",
        (
            "Why did the pickleball hit the net? It wanted to see what was on the "
            "other side."
        ),
        "How is a pickleball game like a waiter? They both serve.",
        (
            "Why should you never fall in love with a tennis player? To them, 'Love' "
            "means nothing."
        ),
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
            # Record outcome for form calculation (last 5 games)
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
        # matches are processed in descending order, so first 5 are most recent
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

        # Build enriched entry for template filters
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
    # Matches must be sorted descending for form calculation to work as currently
    # implemented
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
            # Rank is inverted: lower is better. last_week_rank=1, current_rank=2
            # -> change is -1 (down)
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
    """Calculate the leaderboard for a specific group using Firestore.

    This implementation uses the 'groupId' field on matches.
    It supports both singles and doubles matches.
    """
    db = firestore.client()
    group_ref = db.collection("groups").document(group_id)
    group = group_ref.get()
    if not group.exists:
        return []

    group_data = group.to_dict()
    member_refs = group_data.get("members", [])
    if not member_refs:
        return []

    # Fetch all matches for this group
    all_matches_stream = (
        db.collection("matches")
        .where(filter=FieldFilter("groupId", "==", group_id))
        .stream()
    )
    all_matches = list(all_matches_stream)

    # Calculate current leaderboard
    current_leaderboard = _calculate_leaderboard_from_matches(all_matches, member_refs)

    # Calculate leaderboard from a week ago for rank trend
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

    # Sort matches by date descending for streak calculation
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

    # Fill in any missing trailing dates
    for ds in datasets_dict.values():
        while len(ds["data"]) < len(unique_dates):
            ds["data"].append(ds["data"][-1] if ds["data"] else None)

    return {"labels": unique_dates, "datasets": list(datasets_dict.values())}


def _calculate_all_time_streaks(matches: list[Any], user_ref: Any) -> tuple[int, int]:
    """Calculate current and longest winning streaks for a user."""
    # Matches should be sorted chronologically for all-time streak
    matches.sort(key=lambda x: x.to_dict().get("matchDate") or datetime.min)
    current = longest = 0

    for match in matches:
        data = match.to_dict()
        p1_score, p2_score = _get_match_scores(data)
        team1_ids, team2_ids = _extract_team_ids(data)

        # Handle both Ref (new) and ID (old) for user_ref comparison
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


def send_invite_email_background(
    app: Flask, invite_token: str, email_data: dict[str, Any]
) -> None:
    """Send an invite email in a background thread."""

    def task() -> None:
        """Perform the email sending task in the background."""
        with app.app_context():
            db = firestore.client()
            invite_ref = db.collection("group_invites").document(invite_token)
            try:
                # We need to render the template inside the app context if it
                # wasn't pre-rendered. send_email takes a template name and
                # kwargs.
                send_email(**email_data)
                invite_ref.update(
                    {"status": "sent", "last_error": firestore.DELETE_FIELD}
                )
            except Exception as e:
                # Log the full exception to stderr so it shows up in Docker logs
                print(f"ERROR: Background invite email failed: {e}", file=sys.stderr)
                # Store the error message
                invite_ref.update({"status": "failed", "last_error": str(e)})

    thread = threading.Thread(target=task)
    thread.start()


def friend_group_members(db: Any, group_id: str, new_member_ref: Any) -> None:
    """Automatically create friend relationships between group members.

    Automatically create friend relationships between the new member and existing
    group members.
    """
    group_ref = db.collection("groups").document(group_id)
    group_doc = group_ref.get()
    if not group_doc.exists:
        return

    group_data = group_doc.to_dict()
    member_refs = group_data.get("members", [])

    if not member_refs:
        return

    batch = db.batch()
    new_member_id = new_member_ref.id
    operation_count = 0

    for member_ref in member_refs:
        if member_ref.id == new_member_id:
            continue

        # Add friend for new member
        new_member_friend_ref = new_member_ref.collection("friends").document(
            member_ref.id
        )
        # Add friend for existing member
        existing_member_friend_ref = member_ref.collection("friends").document(
            new_member_id
        )

        batch.set(
            new_member_friend_ref,
            {"status": "accepted", "initiator": True},
            merge=True,
        )
        batch.set(
            existing_member_friend_ref,
            {"status": "accepted", "initiator": False},
            merge=True,
        )
        operation_count += 2

        # Commit batch if it gets too large (Firestore limit is 500)
        if operation_count >= FIRESTORE_BATCH_LIMIT:
            batch.commit()
            batch = db.batch()
            operation_count = 0

    if operation_count > 0:
        try:
            batch.commit()
        except Exception as e:
            print(f"Error friending group members: {e}", file=sys.stderr)


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