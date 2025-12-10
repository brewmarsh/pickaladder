"""Utility functions for the group blueprint."""

import threading

from firebase_admin import firestore

from pickaladder.utils import send_email


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
        db.collection("matches")
        .where(filter=firestore.FieldFilter("groupId", "==", group_id))
        .stream()
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

    # Sort the leaderboard by wins
    leaderboard.sort(key=lambda x: x["wins"], reverse=True)
    return leaderboard


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
                # Store the error message
                invite_ref.update({"status": "failed", "last_error": str(e)})

    thread = threading.Thread(target=task)
    thread.start()
