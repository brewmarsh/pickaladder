"""Utility functions for the group blueprint."""

import secrets
import threading
from datetime import datetime

from firebase_admin import firestore

from pickaladder.utils import send_email


def get_random_joke():
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


def get_group_leaderboard(group_id):
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

    # In-memory store for player stats
    player_stats = {
        ref.id: {
            "wins": 0,
            "losses": 0,
            "games": 0,
            "total_score": 0,
            "user_data": ref.get(),
        }
        for ref in member_refs
    }

    # Fetch pending invites and add to player_stats
    invites_query = (
        db.collection("group_invites")
        .where("group_id", "==", group_id)
        .where("used", "==", False)
        .stream()
    )
    invited_emails = {
        doc.to_dict().get("email")
        for doc in invites_query
        if doc.to_dict().get("email")
    }

    if invited_emails:
        invited_emails_list = list(invited_emails)
        # Find users matching these emails (chunks of 30)
        for i in range(0, len(invited_emails_list), 30):
            batch_emails = invited_emails_list[i : i + 30]
            users_by_email = (
                db.collection("users").where("email", "in", batch_emails).stream()
            )
            for user_doc in users_by_email:
                if user_doc.id not in player_stats:
                    player_stats[user_doc.id] = {
                        "wins": 0,
                        "losses": 0,
                        "games": 0,
                        "total_score": 0,
                        "user_data": user_doc,
                    }

    # Helper function to update stats
    def update_player_stats(player_id, score, is_winner, is_draw=False):
        if player_id in player_stats:
            player_stats[player_id]["games"] += 1
            player_stats[player_id]["total_score"] += score
            if is_winner:
                player_stats[player_id]["wins"] += 1
            elif not is_draw:
                player_stats[player_id]["losses"] += 1

    # Fetch all matches for this group
    matches_in_group = (
        db.collection("matches").where("groupId", "==", group_id).stream()
    )

    for match in matches_in_group:
        data = match.to_dict()
        match_type = data.get("matchType", "singles")
        p1_score = data.get("player1Score", 0)
        p2_score = data.get("player2Score", 0)

        # Determine winner
        p1_wins = p1_score > p2_score
        p2_wins = p2_score > p1_score
        is_draw = p1_score == p2_score

        if match_type == "doubles":
            # Team 1
            team1 = data.get("team1", [])
            for ref in team1:
                update_player_stats(ref.id, p1_score, p1_wins, is_draw)

            # Team 2
            team2 = data.get("team2", [])
            for ref in team2:
                update_player_stats(ref.id, p2_score, p2_wins, is_draw)

        else:
            # Singles
            p1_ref = data.get("player1Ref")
            p2_ref = data.get("player2Ref")

            if p1_ref:
                update_player_stats(p1_ref.id, p1_score, p1_wins, is_draw)
            if p2_ref:
                update_player_stats(p2_ref.id, p2_score, p2_wins, is_draw)

    # Format the leaderboard data
    leaderboard = []
    for user_id, stats in player_stats.items():
        user_doc = stats["user_data"]
        if not user_doc.exists:
            continue

        user_data = user_doc.to_dict()
        games_played = stats["games"]
        avg_score = stats["total_score"] / games_played if games_played > 0 else 0.0
        leaderboard.append(
            {
                "id": user_id,
                "name": user_data.get("name", "N/A"),
                "wins": stats["wins"],
                "losses": stats["losses"],
                "games_played": stats["games"],
                "avg_score": avg_score,
            }
        )

    # Sort the leaderboard by avg_score, then wins, then games_played
    leaderboard.sort(
        key=lambda x: (x["avg_score"], x["wins"], x["games_played"]), reverse=True
    )
    return leaderboard


def get_leaderboard_trend_data(group_id):
    """Generate data for a leaderboard trend chart."""
    db = firestore.client()
    matches_query = db.collection("matches").where("groupId", "==", group_id)
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
    trend_data = {"labels": [], "datasets": {}}

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


def get_user_group_stats(group_id, user_id):
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
    matches_query = db.collection("matches").where("groupId", "==", group_id)
    user_ref = db.collection("users").document(user_id)
    all_matches = list(matches_query.stream())
    all_matches.sort(key=lambda x: x.to_dict().get("matchDate") or datetime.min)

    current_streak = 0
    longest_streak = 0

    for match in all_matches:
        data = match.to_dict()
        match_type = data.get("matchType", "singles")
        p1_score = data.get("player1Score", 0)
        p2_score = data.get("player2Score", 0)

        user_is_winner = False
        user_participated = False

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
                if current_streak > longest_streak:
                    longest_streak = current_streak
                current_streak = 0

    if current_streak > longest_streak:
        longest_streak = current_streak

    stats["longest_streak"] = longest_streak
    stats["win_streak"] = current_streak

    return stats


def send_invite_email_background(app, invite_token, email_data):
    """Send an invite email in a background thread."""

    def task():
        with app.app_context():
            db = firestore.client()
            invite_ref = db.collection("group_invites").document(invite_token)
            try:
                # We need to render the template inside the app context if it wasn't pre-rendered.
                # send_email takes a template name and kwargs.
                send_email(**email_data)
                invite_ref.update(
                    {"status": "sent", "last_error": firestore.DELETE_FIELD}
                )
            except Exception as e:
                import sys

                # Log the full exception to stderr so it shows up in Docker logs
                print(f"ERROR: Background invite email failed: {e}", file=sys.stderr)
                # Store the error message
                invite_ref.update({"status": "failed", "last_error": str(e)})

    thread = threading.Thread(target=task)
    thread.start()


def friend_group_members(db, group_id, new_member_ref):
    """Automatically create friend relationships between the new member and existing group members."""
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
        if operation_count >= 400:
            batch.commit()
            batch = db.batch()
            operation_count = 0

    if operation_count > 0:
        try:
            batch.commit()
        except Exception as e:
            import sys

            print(f"Error friending group members: {e}", file=sys.stderr)
