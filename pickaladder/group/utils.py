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

from pickaladder.user.helpers import smart_display_name
from pickaladder.utils import send_email

FIRESTORE_BATCH_LIMIT = 400
RECENT_MATCHES_LIMIT = 5
HOT_STREAK_THRESHOLD = 3


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
            # Record outcome for form calculation (last 5 games)
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

    # Create a map of user_id to last week's rank
    last_week_ranks = {
        player["id"]: i + 1 for i, player in enumerate(last_week_leaderboard)
    }

    # Add rank change to current leaderboard
    for i, player in enumerate(current_leaderboard):
        current_rank = i + 1
        last_week_rank = last_week_ranks.get(player["id"])
        if last_week_rank is not None:
            # Rank is inverted: lower is better. last_week_rank=1, current_rank=2
            # -> change is -1 (down)
            player["rank_change"] = last_week_rank - current_rank
        else:
            # Player was not on the leaderboard last week, or had no rank
            player["rank_change"] = "new"

    # --- Calculate Winning Streaks ---
    # Sort all matches by date once, descending to check recent matches first
    all_matches.sort(
        key=lambda m: m.to_dict().get("matchDate") or datetime.min, reverse=True
    )

    # Pre-process matches to map users to their matches
    user_matches_map: dict[str, list[dict[str, Any]]] = {
        ref.id: [] for ref in member_refs
    }
    for match in all_matches:
        data = match.to_dict()
        match_type = data.get("matchType", "singles")
        if match_type == "doubles":
            for ref in data.get("team1", []):
                if ref.id in user_matches_map:
                    user_matches_map[ref.id].append(data)
            for ref in data.get("team2", []):
                if ref.id in user_matches_map:
                    user_matches_map[ref.id].append(data)
        else:
            p1_ref = data.get("player1Ref")
            p2_ref = data.get("player2Ref")
            if p1_ref and p1_ref.id in user_matches_map:
                user_matches_map[p1_ref.id].append(data)
            if p2_ref and p2_ref.id in user_matches_map:
                user_matches_map[p2_ref.id].append(data)

    for player in current_leaderboard:
        streak = 0
        user_id = player["id"]

        for match_data in user_matches_map.get(user_id, []):
            p1_score = match_data.get("player1Score", 0)
            p2_score = match_data.get("player2Score", 0)
            p1_wins = p1_score > p2_score
            p2_wins = p2_score > p1_score
            is_draw = p1_score == p2_score

            if is_draw:
                break  # Streak ends with a draw

            user_won = False
            match_type = match_data.get("matchType", "singles")
            if match_type == "doubles":
                team1_ids = [ref.id for ref in match_data.get("team1", [])]
                team2_ids = [ref.id for ref in match_data.get("team2", [])]
                if user_id in team1_ids:
                    if p1_wins:
                        user_won = True
                elif user_id in team2_ids:
                    if p2_wins:
                        user_won = True
            else:  # Singles
                p1_ref = match_data.get("player1Ref")
                p2_ref = match_data.get("player2Ref")
                if p1_ref and p1_ref.id == user_id:
                    if p1_wins:
                        user_won = True
                elif p2_ref and p2_ref.id == user_id:
                    if p2_wins:
                        user_won = True

            if user_won:
                streak += 1
            else:
                # As soon as a loss is found, the streak is broken
                break

        player["streak"] = streak
        player["is_on_fire"] = streak >= HOT_STREAK_THRESHOLD

    return current_leaderboard


def get_leaderboard_trend_data(group_id: str) -> dict[str, Any]:
    """Generate data for a leaderboard trend chart."""
    db = firestore.client()
    matches_query = db.collection("matches").where(
        filter=FieldFilter("groupId", "==", group_id)
    )
    # Filter and sort in Python to avoid composite index requirement
    # Use to_dict().get() to safely handle missing fields without KeyError
    matches = [m for m in matches_query.stream() if m.to_dict().get("matchDate")]
    matches.sort(key=lambda x: x.to_dict().get("matchDate"))
    if not matches:
        return {"labels": [], "datasets": []}

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

    player_stats = {ref.id: {"total_score": 0, "games": 0} for ref in all_player_refs}
    trend_data: dict[str, Any] = {"labels": [], "datasets": {}}

    for player_id, player_info in players_data.items():
        trend_data["datasets"][player_id] = {
            "label": player_info["name"],
            "data": [],
            "fill": False,
            "profilePictureUrl": player_info["profilePictureUrl"],
        }

    unique_dates = sorted(
        list({m.to_dict().get("matchDate").strftime("%Y-%m-%d") for m in matches})
    )
    trend_data["labels"] = unique_dates

    date_idx = 0
    for i, match in enumerate(matches):
        data = match.to_dict()
        match_date = data.get("matchDate").strftime("%Y-%m-%d")

        while date_idx < len(unique_dates) and unique_dates[date_idx] < match_date:
            for player_id in player_stats:
                avg_score = (
                    player_stats[player_id]["total_score"]
                    / player_stats[player_id]["games"]
                    if player_stats[player_id]["games"] > 0
                    else None
                )
                trend_data["datasets"][player_id]["data"].append(avg_score)
            date_idx += 1

        if data.get("matchType", "singles") == "doubles":
            for ref in data.get("team1", []):
                player_stats[ref.id]["total_score"] += data.get("player1Score", 0)
                player_stats[ref.id]["games"] += 1
            for ref in data.get("team2", []):
                player_stats[ref.id]["total_score"] += data.get("player2Score", 0)
                player_stats[ref.id]["games"] += 1
        else:
            p1_ref, p2_ref = data.get("player1Ref"), data.get("player2Ref")
            if p1_ref:
                player_stats[p1_ref.id]["total_score"] += data.get("player1Score", 0)
                player_stats[p1_ref.id]["games"] += 1
            if p2_ref:
                player_stats[p2_ref.id]["total_score"] += data.get("player2Score", 0)
                player_stats[p2_ref.id]["games"] += 1

        if (
            i == len(matches) - 1
            or matches[i + 1].to_dict().get("matchDate").strftime("%Y-%m-%d")
            != match_date
        ):
            for player_id in player_stats:
                avg_score = (
                    player_stats[player_id]["total_score"]
                    / player_stats[player_id]["games"]
                    if player_stats[player_id]["games"] > 0
                    else None
                )
                trend_data["datasets"][player_id]["data"].append(avg_score)
            date_idx += 1

    for ds in trend_data["datasets"].values():
        while len(ds["data"]) < len(unique_dates):
            ds["data"].append(ds["data"][-1] if ds["data"] else None)

    trend_data["datasets"] = list(trend_data["datasets"].values())
    return trend_data


def get_user_group_stats(group_id: str, user_id: str) -> dict[str, Any]:
    """Calculate detailed statistics for a specific user within a group."""
    db = firestore.client()
    stats = {
        "rank": "N/A",
        "wins": 0,
        "losses": 0,
        "win_streak": 0,
        "longest_streak": 0,
    }

    # --- Calculate Rank ---
    leaderboard = get_group_leaderboard(group_id)
    for i, player in enumerate(leaderboard):
        if player["id"] == user_id:
            stats["rank"] = i + 1
            stats["wins"] = player.get("wins", 0)
            stats["losses"] = player.get("losses", 0)
            break

    # --- Calculate Win Streaks ---
    matches_query = db.collection("matches").where(
        filter=FieldFilter("groupId", "==", group_id)
    )
    user_ref = db.collection("users").document(user_id)
    all_matches = list(matches_query.stream())
    all_matches.sort(key=lambda x: x.to_dict().get("matchDate") or datetime.min)

    current_streak = longest_streak = 0

    for match in all_matches:
        data = match.to_dict()
        match_type = data.get("matchType", "singles")
        p1_score = data.get("player1Score", 0)
        p2_score = data.get("player2Score", 0)

        user_is_winner = user_participated = False

        if match_type == "doubles":
            team1 = data.get("team1", [])
            team2 = data.get("team2", [])
            if user_ref in team1:
                user_participated = True
                if p1_score > p2_score:
                    user_is_winner = True
            elif user_ref in team2:
                user_participated = True
                if p2_score > p1_score:
                    user_is_winner = True
        else:  # Singles
            p1_ref = data.get("player1Ref")
            p2_ref = data.get("player2Ref")
            if user_ref == p1_ref:
                user_participated = True
                if p1_score > p2_score:
                    user_is_winner = True
            elif user_ref == p2_ref:
                user_participated = True
                if p2_score > p1_score:
                    user_is_winner = True

        if user_participated:
            if user_is_winner:
                current_streak += 1
            else:
                longest_streak = max(longest_streak, current_streak)
                current_streak = 0

    longest_streak = max(longest_streak, current_streak)

    stats["longest_streak"] = longest_streak
    stats["win_streak"] = current_streak

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
    """
    Calculates the win/loss record for two players when they are partners.

    Args:
        playerA_id: The ID of the first player.
        playerB_id: The ID of the second player.
        all_matches_in_group: A list of match documents from Firestore.

    Returns:
        A dictionary with 'wins' and 'losses' for the partnership.
    """
    wins = 0
    losses = 0

    for match_doc in all_matches_in_group:
        data = match_doc.to_dict()
        if data.get("matchType") != "doubles":
            continue

        # Extract team member IDs, handling both old (IDs) and new (Refs) formats
        team1_ids = set()
        if "team1" in data:  # New format: list of refs
            team1_ids = {ref.id for ref in data["team1"] if hasattr(ref, "id")}
        else:  # Old format
            team1_ids = {data.get("player1Id"), data.get("partnerId")}

        team2_ids = set()
        if "team2" in data:  # New format: list of refs
            team2_ids = {ref.id for ref in data["team2"] if hasattr(ref, "id")}
        else:  # Old format
            team2_ids = {data.get("player2Id"), data.get("opponent2Id")}

        team1_ids.discard(None)
        team2_ids.discard(None)

        # Check for partnership
        partnership_team1 = {playerA_id, playerB_id}.issubset(team1_ids)
        partnership_team2 = {playerA_id, playerB_id}.issubset(team2_ids)

        p1_score = data.get("player1Score")
        if p1_score is None:
            p1_score = data.get("team1Score", 0)
        p2_score = data.get("player2Score")
        if p2_score is None:
            p2_score = data.get("team2Score", 0)

        if partnership_team1:
            if p1_score > p2_score:
                wins += 1
            elif p2_score > p1_score:
                losses += 1
        elif partnership_team2:
            if p2_score > p1_score:
                wins += 1
            elif p1_score > p2_score:
                losses += 1

    return {"wins": wins, "losses": losses}


def get_head_to_head_stats(
    group_id: str, playerA_id: str, playerB_id: str
) -> dict[str, Any]:
    """
    Calculates head-to-head statistics for two players in doubles matches.

    Args:
        group_id: The ID of the group to search for matches in.
        playerA_id: The ID of the first player.
        playerB_id: The ID of the second player.

    Returns:
        A dictionary containing wins for player A, losses for player A,
        a list of the matches played between them, and the point differential.
    """
    db = firestore.client()
    matches_ref = db.collection("matches")

    query = matches_ref.where(filter=FieldFilter("groupId", "==", group_id))
    all_matches_in_group = list(query.stream())

    # Calculate partnership stats first
    partnership_record = get_partnership_stats(
        playerA_id, playerB_id, all_matches_in_group
    )

    wins = 0
    losses = 0
    point_diff = 0
    playerA_total_points = 0
    playerB_total_points = 0
    rivalry_matches = []

    for match_doc in all_matches_in_group:
        data = match_doc.to_dict()

        # Extract team member IDs, handling both old (IDs) and new (Refs) formats
        team1_ids = set()
        if "team1" in data:  # New format: list of refs
            team1_ids = {ref.id for ref in data["team1"] if hasattr(ref, "id")}
        else:  # Old format
            team1_ids = {data.get("player1Id"), data.get("partnerId")}

        team2_ids = set()
        if "team2" in data:  # New format: list of refs
            team2_ids = {ref.id for ref in data["team2"] if hasattr(ref, "id")}
        else:  # Old format
            team2_ids = {data.get("player2Id"), data.get("opponent2Id")}

        team1_ids.discard(None)
        team2_ids.discard(None)

        participants = team1_ids.union(team2_ids)
        if playerA_id not in participants or playerB_id not in participants:
            continue

        player_a_is_team1 = playerA_id in team1_ids
        player_b_is_team2 = playerB_id in team2_ids

        player_a_is_team2 = playerA_id in team2_ids
        player_b_is_team1 = playerB_id in team1_ids

        if (player_a_is_team1 and player_b_is_team2) or (
            player_a_is_team2 and player_b_is_team1
        ):
            # For display in 'Recent Clashes', we need to ensure some fields are present
            match_display_data = data.copy()
            match_display_data["id"] = match_doc.id

            # Pass the extracted IDs back for template compatibility
            match_display_data["team1_ids"] = list(team1_ids)
            match_display_data["team2_ids"] = list(team2_ids)

            rivalry_matches.append(match_display_data)

            team1_score = data.get("player1Score")
            if team1_score is None:
                team1_score = data.get("team1Score", 0)
            team2_score = data.get("player2Score")
            if team2_score is None:
                team2_score = data.get("team2Score", 0)

            if player_a_is_team1:
                point_diff += team1_score - team2_score
                playerA_total_points += team1_score
                playerB_total_points += team2_score
                if team1_score > team2_score:
                    wins += 1
                elif team2_score > team1_score:
                    losses += 1
            else:  # Player A is on team 2
                point_diff += team2_score - team1_score
                playerA_total_points += team2_score
                playerB_total_points += team1_score
                if team2_score > team1_score:
                    wins += 1
                elif team1_score > team2_score:
                    losses += 1

    num_matches = len(rivalry_matches)
    avg_points_A = playerA_total_points / num_matches if num_matches > 0 else 0
    avg_points_B = playerB_total_points / num_matches if num_matches > 0 else 0

    return {
        "wins": wins,
        "losses": losses,
        "matches": rivalry_matches,
        "point_diff": point_diff,
        "avg_points_scored": {
            "playerA": avg_points_A,
            "playerB": avg_points_B,
        },
        "partnership_record": partnership_record,
    }
