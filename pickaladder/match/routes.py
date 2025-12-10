"""Routes for the match blueprint."""

import datetime

from firebase_admin import firestore
from flask import flash, g, redirect, render_template, request, url_for

from pickaladder.auth.decorators import login_required

from . import bp
from .forms import MatchForm


def get_player_record(player_ref):
    """Calculate the win/loss record for a given player by their document reference."""
    db = firestore.client()
    wins = 0
    losses = 0

    # 1. Matches where the user is player1 (Singles)
    p1_matches_query = (
        db.collection("matches")
        .where(filter=firestore.FieldFilter("player1Ref", "==", player_ref))
        .stream()
    )
    for match in p1_matches_query:
        data = match.to_dict()
        # Skip if it's a doubles match misclassified (shouldn't happen with correct queries but safe)
        if data.get("matchType") == "doubles":
            continue

        if data.get("player1Score", 0) > data.get("player2Score", 0):
            wins += 1
        else:
            losses += 1

    # 2. Matches where the user is player2 (Singles)
    p2_matches_query = (
        db.collection("matches")
        .where(filter=firestore.FieldFilter("player2Ref", "==", player_ref))
        .stream()
    )
    for match in p2_matches_query:
        data = match.to_dict()
        if data.get("matchType") == "doubles":
            continue

        if data.get("player2Score", 0) > data.get("player1Score", 0):
            wins += 1
        else:
            losses += 1

    # 3. Matches where the user is in team1 (Doubles)
    # Note: 'array_contains' is the correct filter operator for array membership
    t1_matches_query = (
        db.collection("matches")
        .where(filter=firestore.FieldFilter("team1", "array_contains", player_ref))
        .stream()
    )
    for match in t1_matches_query:
        data = match.to_dict()
        # Ensure it is actually a doubles match
        if data.get("matchType") != "doubles":
            continue

        if data.get("player1Score", 0) > data.get("player2Score", 0):
            wins += 1
        else:
            losses += 1

    # 4. Matches where the user is in team2 (Doubles)
    t2_matches_query = (
        db.collection("matches")
        .where(filter=firestore.FieldFilter("team2", "array_contains", player_ref))
        .stream()
    )
    for match in t2_matches_query:
        data = match.to_dict()
        if data.get("matchType") != "doubles":
            continue

        if data.get("player2Score", 0) > data.get("player1Score", 0):
            wins += 1
        else:
            losses += 1

    return {"wins": wins, "losses": losses}


@bp.route("/<string:match_id>")
@login_required
def view_match_page(match_id):
    """Display the details of a single match."""
    db = firestore.client()
    match_ref = db.collection("matches").document(match_id)
    match = match_ref.get()
    if not match.exists:
        flash("Match not found.", "danger")
        return redirect(url_for("user.dashboard"))

    match_data = match.to_dict()
    match_type = match_data.get("matchType", "singles")

    context = {"match": match_data, "match_type": match_type}

    if match_type == "doubles":
        # Fetch team members
        # team1 and team2 are lists of refs
        team1_refs = match_data.get("team1", [])
        team2_refs = match_data.get("team2", [])

        team1_data = []
        for ref in team1_refs:
            p = ref.get()
            if p.exists:
                team1_data.append(p.to_dict())

        team2_data = []
        for ref in team2_refs:
            p = ref.get()
            if p.exists:
                team2_data.append(p.to_dict())

        context["team1"] = team1_data
        context["team2"] = team2_data

    else:
        # Fetch player data from references
        # Handle cases where refs might be missing in corrupted data
        player1_ref = match_data.get("player1Ref")
        player2_ref = match_data.get("player2Ref")

        player1_data = {}
        player2_data = {}
        player1_record = {"wins": 0, "losses": 0}
        player2_record = {"wins": 0, "losses": 0}

        if player1_ref:
            player1 = player1_ref.get()
            if player1.exists:
                player1_data = player1.to_dict()
                player1_record = get_player_record(player1_ref)

        if player2_ref:
            player2 = player2_ref.get()
            if player2.exists:
                player2_data = player2.to_dict()
                player2_record = get_player_record(player2_ref)

        context.update(
            {
                "player1": player1_data,
                "player2": player2_data,
                "player1_record": player1_record,
                "player2_record": player2_record,
            }
        )

    return render_template("view_match.html", **context)


@bp.route("/create", methods=["GET", "POST"])
@login_required
def create_match():
    """Create a new match."""
    db = firestore.client()
    user_id = g.user["uid"]
    form = MatchForm()
    group_id = request.args.get("group_id")

    # Collect all potential player IDs
    candidate_player_ids = set()

    # 1. Group Members (if group_id is provided)
    if group_id:
        group_ref = db.collection("groups").document(group_id)
        group = group_ref.get()
        if group.exists:
            group_data = group.to_dict()
            member_refs = group_data.get("members", [])
            for ref in member_refs:
                candidate_player_ids.add(ref.id)

            # 3. Pending Group Invites (users who have been invited but haven't joined)
            invites_query = (
                db.collection("group_invites")
                .where(filter=firestore.FieldFilter("group_id", "==", group_id))
                .where(filter=firestore.FieldFilter("used", "==", False))
                .stream()
            )
            invited_emails = [doc.to_dict().get("email") for doc in invites_query]

            if invited_emails:
                # Find users matching these emails
                # Note: 'in' query supports up to 30 items. We batch if necessary.
                # For simplicity, we'll take chunks of 30.
                for i in range(0, len(invited_emails), 30):
                    batch_emails = invited_emails[i : i + 30]
                    users_by_email = (
                        db.collection("users")
                        .where(
                            filter=firestore.FieldFilter("email", "in", batch_emails)
                        )
                        .stream()
                    )
                    for user_doc in users_by_email:
                        candidate_player_ids.add(user_doc.id)

    # 2. Friends and other invites (only if not in a group context)
    if not group_id:
        friends_ref = db.collection("users").document(user_id).collection("friends")
        friends_docs = friends_ref.stream()
        for doc in friends_docs:
            if doc.to_dict().get("status") in ["accepted", "pending"]:
                candidate_player_ids.add(doc.id)

        # 3. Users invited to any group by the current user
        my_invites_query = (
            db.collection("group_invites")
            .where(filter=firestore.FieldFilter("inviter_id", "==", user_id))
            .stream()
        )
        my_invited_emails = {doc.to_dict().get("email") for doc in my_invites_query}

        if my_invited_emails:
            # Find users matching these emails
            my_invited_emails_list = list(my_invited_emails)
            for i in range(0, len(my_invited_emails_list), 10):
                batch_emails = my_invited_emails_list[i : i + 10]
                users_by_email = (
                    db.collection("users")
                    .where(filter=firestore.FieldFilter("email", "in", batch_emails))
                    .stream()
                )
                for user_doc in users_by_email:
                    candidate_player_ids.add(user_doc.id)

    # Remove current user from candidates
    candidate_player_ids.discard(user_id)

    # Fetch user details for all candidates
    player_choices = []
    if candidate_player_ids:
        # Fetch users in batches of 30 (Firestore 'in' limit)
        candidate_ids_list = list(candidate_player_ids)
        for i in range(0, len(candidate_ids_list), 30):
            batch_ids = candidate_ids_list[i : i + 30]
            # Convert IDs to DocumentReferences for __name__ query
            batch_refs = [db.collection("users").document(uid) for uid in batch_ids]

            users_query = (
                db.collection("users")
                .where(filter=firestore.FieldFilter("__name__", "in", batch_refs))
                .stream()
            )
            for user_doc in users_query:
                player_choices.append(
                    (user_doc.id, user_doc.to_dict().get("name", user_doc.id))
                )

    # Populate all select fields
    form.player2.choices = player_choices
    form.partner.choices = player_choices
    form.opponent2.choices = player_choices

    # Default match type logic
    user_ref = db.collection("users").document(user_id)
    if request.method == "GET":
        user_data = user_ref.get().to_dict()
        last_match_type = user_data.get("lastMatchRecordedType")
        if last_match_type:
            form.match_type.data = last_match_type

    if form.validate_on_submit():
        try:
            match_date = form.match_date.data or datetime.date.today()
            if isinstance(match_date, datetime.date) and not isinstance(
                match_date, datetime.datetime
            ):
                match_date = datetime.datetime.combine(match_date, datetime.time.min)

            match_data = {
                "player1Score": form.player1_score.data,
                "player2Score": form.player2_score.data,
                "matchDate": match_date,
                "createdAt": firestore.SERVER_TIMESTAMP,
                "matchType": form.match_type.data,
            }

            if group_id:
                match_data["groupId"] = group_id

            if form.match_type.data == "singles":
                player1_ref = db.collection("users").document(user_id)
                player2_ref = db.collection("users").document(form.player2.data)
                match_data["player1Ref"] = player1_ref
                match_data["player2Ref"] = player2_ref

            elif form.match_type.data == "doubles":
                # Team 1: Current User + Partner
                t1_p1_ref = db.collection("users").document(user_id)
                t1_p2_ref = db.collection("users").document(form.partner.data)

                # Team 2: Opponent 1 (player2 field) + Opponent 2
                t2_p1_ref = db.collection("users").document(form.player2.data)
                t2_p2_ref = db.collection("users").document(form.opponent2.data)

                match_data["team1"] = [t1_p1_ref, t1_p2_ref]
                match_data["team2"] = [t2_p1_ref, t2_p2_ref]

            db.collection("matches").add(match_data)

            # Update last match type
            user_ref.update({"lastMatchRecordedType": form.match_type.data})

            flash("Match created successfully.", "success")
            if group_id:
                return redirect(url_for("group.view_group", group_id=group_id))
            return redirect(url_for("user.dashboard"))
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")

    return render_template("create_match.html", form=form)


@bp.route("/leaderboard")
@login_required
def leaderboard():
    """Display a global leaderboard.

    Note: This is a simplified, non-scalable implementation. A production-ready
    leaderboard on Firestore would likely require denormalization and Cloud Functions.
    """
    db = firestore.client()
    try:
        users_query = db.collection("users").limit(50).stream()
        players = []
        for user in users_query:
            user_data = user.to_dict()
            user_ref = db.collection("users").document(user.id)
            record = get_player_record(user_ref)

            win_percentage = 0
            games_played = record["wins"] + record["losses"]
            if games_played > 0:
                win_percentage = (record["wins"] / games_played) * 100

            players.append(
                {
                    "id": user.id,
                    "name": user_data.get("name", "N/A"),
                    "wins": record["wins"],
                    "losses": record["losses"],
                    "games_played": games_played,
                    "win_percentage": win_percentage,
                }
            )

        # Sort players by win percentage, then by wins
        players.sort(key=lambda p: (p["win_percentage"], p["wins"]), reverse=True)

    except Exception as e:
        players = []
        flash(f"An error occurred while fetching the leaderboard: {e}", "danger")

    return render_template(
        "leaderboard.html", players=players, current_user_id=g.user["uid"]
    )
