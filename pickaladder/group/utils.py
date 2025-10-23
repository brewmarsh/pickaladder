from firebase_admin import firestore


def get_group_leaderboard(group_id):
    """
    Calculates the leaderboard for a specific group using Firestore.
    This is a client-side implementation of the aggregation logic.
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

    # Fetch all matches where both players are members of the group.
    # This requires two separate queries.
    matches_p1_in_group = (
        db.collection("matches")
        .where(filter=firestore.FieldFilter("player1Ref", "in", member_refs))
        .stream()
    )
    matches_p2_in_group = (
        db.collection("matches")
        .where(filter=firestore.FieldFilter("player2Ref", "in", member_refs))
        .stream()
    )

    # In-memory store for player stats
    player_stats = {
        ref.id: {"wins": 0, "losses": 0, "games": 0, "user_data": ref.get()}
        for ref in member_refs
    }

    # Process matches where at least one player is in the group
    all_matches = list(matches_p1_in_group) + list(matches_p2_in_group)
    processed_match_ids = set()

    for match in all_matches:
        if match.id in processed_match_ids:
            continue
        processed_match_ids.add(match.id)

        data = match.to_dict()
        p1_ref = data.get("player1Ref")
        p2_ref = data.get("player2Ref")

        # Ensure both players are in the group before counting the match
        if p1_ref not in member_refs or p2_ref not in member_refs:
            continue

        p1_id = p1_ref.id
        p2_id = p2_ref.id
        p1_score = data.get("player1Score", 0)
        p2_score = data.get("player2Score", 0)

        # Update stats for Player 1
        player_stats[p1_id]["games"] += 1
        if p1_score > p2_score:
            player_stats[p1_id]["wins"] += 1
        else:
            player_stats[p1_id]["losses"] += 1

        # Update stats for Player 2
        player_stats[p2_id]["games"] += 1
        if p2_score > p1_score:
            player_stats[p2_id]["wins"] += 1
        else:
            player_stats[p2_id]["losses"] += 1

    # Format the leaderboard data
    leaderboard = []
    for user_id, stats in player_stats.items():
        user_doc = stats["user_data"]
        if user_doc.exists:
            user_data = user_doc.to_dict()
            leaderboard.append(
                {
                    "id": user_id,
                    "name": user_data.get("name", "N/A"),
                    "wins": stats["wins"],
                    "losses": stats["losses"],
                    "games_played": stats["games"],
                }
            )

    # Sort the leaderboard by wins
    leaderboard.sort(key=lambda x: x["wins"], reverse=True)
    return leaderboard
