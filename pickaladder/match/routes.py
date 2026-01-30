"""Routes for the match blueprint."""

import datetime

from firebase_admin import firestore
from flask import flash, g, jsonify, redirect, render_template, request, url_for

from pickaladder.auth.decorators import login_required

from . import bp
from .forms import MatchForm


def _get_candidate_player_ids(user_id, group_id=None, include_user=False):
    """Fetch a set of valid opponent IDs for a user, optionally within a group."""
    db = firestore.client()
    candidate_player_ids = set()

    if group_id:
        # If in a group context, candidates are group members and pending invitees
        group_ref = db.collection("groups").document(group_id)
        group = group_ref.get()
        if group.exists:
            group_data = group.to_dict()
            member_refs = group_data.get("members", [])
            for ref in member_refs:
                candidate_player_ids.add(ref.id)

        invites_query = (
            db.collection("group_invites")
            .where(filter=firestore.FieldFilter("group_id", "==", group_id))
            .where(filter=firestore.FieldFilter("used", "==", False))
            .stream()
        )
        invited_emails = [doc.to_dict().get("email") for doc in invites_query]

        if invited_emails:
            for i in range(0, len(invited_emails), 30):
                batch_emails = invited_emails[i : i + 30]
                users_by_email = (
                    db.collection("users")
                    .where(filter=firestore.FieldFilter("email", "in", batch_emails))
                    .stream()
                )
                for user_doc in users_by_email:
                    candidate_player_ids.add(user_doc.id)
    else:
        # If not in a group context, candidates are friends and user's own invitees
        friends_ref = db.collection("users").document(user_id).collection("friends")
        friends_docs = friends_ref.stream()
        for doc in friends_docs:
            if doc.to_dict().get("status") in ["accepted", "pending"]:
                candidate_player_ids.add(doc.id)

        my_invites_query = (
            db.collection("group_invites")
            .where(filter=firestore.FieldFilter("inviter_id", "==", user_id))
            .stream()
        )
        my_invited_emails = {doc.to_dict().get("email") for doc in my_invites_query}

        if my_invited_emails:
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

    if not include_user:
        candidate_player_ids.discard(user_id)
    return candidate_player_ids


def _save_match_data(player_1_id, form_data, group_id=None):
    """Construct and save a match document to Firestore."""
    db = firestore.client()
    user_ref = db.collection("users").document(player_1_id)

    # Handle both form objects and dictionaries
    def get_data(key):
        if isinstance(form_data, dict):
            return form_data.get(key)
        return getattr(form_data, key).data

    match_type = get_data("match_type")
    match_date_input = get_data("match_date")

    if isinstance(match_date_input, str) and match_date_input:
        match_date = datetime.datetime.strptime(match_date_input, "%Y-%m-%d")
    elif isinstance(match_date_input, datetime.date):
        match_date = datetime.datetime.combine(match_date_input, datetime.time.min)
    else:
        match_date = datetime.datetime.now()

    match_data = {
        "player1Score": int(get_data("player1_score")),
        "player2Score": int(get_data("player2_score")),
        "matchDate": match_date,
        "createdAt": firestore.SERVER_TIMESTAMP,
        "matchType": match_type,
    }

    if group_id:
        match_data["groupId"] = group_id

    if match_type == "singles":
        player1_ref = db.collection("users").document(get_data("player1"))
        player2_ref = db.collection("users").document(get_data("player2"))
        match_data["player1Ref"] = player1_ref
        match_data["player2Ref"] = player2_ref
    elif match_type == "doubles":
        t1_p1_ref = db.collection("users").document(get_data("player1"))
        t1_p2_ref = db.collection("users").document(get_data("partner"))
        t2_p1_ref = db.collection("users").document(get_data("player2"))
        t2_p2_ref = db.collection("users").document(get_data("opponent2"))
        match_data["team1"] = [t1_p1_ref, t1_p2_ref]
        match_data["team2"] = [t2_p1_ref, t2_p2_ref]

    db.collection("matches").add(match_data)
    user_ref.update({"lastMatchRecordedType": match_type})


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
        # Skip if it's a doubles match misclassified (shouldn't happen with
        # correct queries but safe)
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


@bp.route("/record", methods=["GET", "POST"])
@login_required
def record_match():
    """Handle match recording for both web form and optimistic JSON submission."""
    db = firestore.client()
    user_id = g.user["uid"]
    group_id = request.args.get("group_id")
    candidate_player_ids = _get_candidate_player_ids(user_id, group_id)

    if request.method == "POST" and request.is_json:
        data = request.get_json()
        form = MatchForm(data=data)

        # Security check: Ensure all selected players are valid candidates
        selected_players = {data.get("player2")}
        if data.get("match_type") == "doubles":
            selected_players.add(data.get("partner"))
            selected_players.add(data.get("opponent2"))

        if not selected_players.issubset(candidate_player_ids):
            return (
                jsonify({"status": "error", "message": "Invalid opponent selected."}),
                403,
            )

        # Populate choices for validation to work
        form.player1.choices = [(p_id, "") for p_id in candidate_player_ids]
        form.player2.choices = [(p_id, "") for p_id in candidate_player_ids]
        if data.get("match_type") == "doubles":
            form.partner.choices = form.player2.choices
            form.opponent2.choices = form.player2.choices

        if form.validate():
            try:
                _save_match_data(user_id, data, group_id)
                return jsonify({"status": "success", "message": "Match recorded."}), 200
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500
        else:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Validation failed",
                        "errors": form.errors,
                    }
                ),
                400,
            )

    # Standard GET request or form submission
    form = MatchForm()

    # Fetch and populate player choices for the form dropdowns
    player1_candidate_ids = _get_candidate_player_ids(
        user_id, group_id, include_user=True
    )

    player1_choices = []
    if player1_candidate_ids:
        candidate_refs = [
            db.collection("users").document(uid) for uid in player1_candidate_ids
        ]
        users = db.get_all(candidate_refs)
        for user_doc in users:
            if user_doc.exists:
                player1_choices.append(
                    (user_doc.id, user_doc.to_dict().get("name", user_doc.id))
                )

    form.player1.choices = player1_choices

    player_choices = []
    if candidate_player_ids:
        # Batch fetch user data for choices
        candidate_refs = [
            db.collection("users").document(uid) for uid in candidate_player_ids
        ]
        users = db.get_all(candidate_refs)
        for user_doc in users:
            if user_doc.exists:
                player_choices.append(
                    (user_doc.id, user_doc.to_dict().get("name", user_doc.id))
                )

    form.player2.choices = player_choices
    form.partner.choices = player_choices
    form.opponent2.choices = player_choices

    if request.method == "GET":
        form.player1.data = user_id
        user_ref = db.collection("users").document(user_id)
        user_snapshot = user_ref.get()
        if user_snapshot.exists:
            user_data = user_snapshot.to_dict()
            last_match_type = user_data.get("lastMatchRecordedType")
            if last_match_type:
                form.match_type.data = last_match_type

    if form.validate_on_submit():
        player_1_id = request.form.get("player1") or user_id

        # Uniqueness check
        player_ids = [player_1_id, form.player2.data]
        if form.match_type.data == "doubles":
            player_ids.extend([form.partner.data, form.opponent2.data])

        # Filter out empty values and check for duplicates
        active_players = [p for p in player_ids if p]
        if len(active_players) != len(set(active_players)):
            flash("All players must be unique.", "danger")
            return render_template("record_match.html", form=form)

        try:
            _save_match_data(player_1_id, form, group_id)
            flash("Match recorded successfully.", "success")
            if group_id:
                return redirect(url_for("group.view_group", group_id=group_id))
            return redirect(url_for("user.dashboard"))
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")

    return render_template("record_match.html", form=form)


def get_latest_matches(limit=10):
    """Fetch and process the latest matches."""
    db = firestore.client()
    matches_query = (
        db.collection("matches")
        .order_by("createdAt", direction=firestore.Query.DESCENDING)
        .limit(limit)
    )
    matches = list(matches_query.stream())

    player_refs = set()
    for match in matches:
        match_data = match.to_dict()
        if match_data.get("matchType") == "doubles":
            player_refs.update(match_data.get("team1", []))
            player_refs.update(match_data.get("team2", []))
        else:
            if match_data.get("player1Ref"):
                player_refs.add(match_data.get("player1Ref"))
            if match_data.get("player2Ref"):
                player_refs.add(match_data.get("player2Ref"))

    players = {}
    if player_refs:
        player_docs = db.get_all(list(player_refs))
        for doc in player_docs:
            if doc.exists:
                players[doc.id] = doc.to_dict().get("name", "N/A")

    processed_matches = []
    for match in matches:
        match_data = match.to_dict()
        match_date = match_data.get("matchDate")
        if isinstance(match_date, datetime.datetime):
            match_date_formatted = match_date.strftime("%b %d")
        else:
            # Fallback if matchDate is not a datetime object
            match_date_formatted = "N/A"

        score1 = match_data.get("player1Score", 0)
        score2 = match_data.get("player2Score", 0)

        point_diff = abs(score1 - score2)
        close_call = point_diff <= 2

        processed_match = {
            "date": match_date_formatted,
            "point_differential": point_diff,
            "close_call": close_call,
        }

        if match_data.get("matchType") == "doubles":
            team1_refs = match_data.get("team1", [])
            team2_refs = match_data.get("team2", [])
            team1_names = " & ".join([players.get(ref.id, "N/A") for ref in team1_refs])
            team2_names = " & ".join([players.get(ref.id, "N/A") for ref in team2_refs])

            if score1 > score2:
                processed_match["winner_name"] = team1_names
                processed_match["loser_name"] = team2_names
                processed_match["winner_score"] = score1
                processed_match["loser_score"] = score2
            else:
                processed_match["winner_name"] = team2_names
                processed_match["loser_name"] = team1_names
                processed_match["winner_score"] = score2
                processed_match["loser_score"] = score1
        else:  # singles
            p1_ref = match_data.get("player1Ref")
            p2_ref = match_data.get("player2Ref")

            p1_name = players.get(p1_ref.id, "N/A") if p1_ref else "N/A"
            p2_name = players.get(p2_ref.id, "N/A") if p2_ref else "N/A"

            if score1 > score2:
                processed_match["winner_name"] = p1_name
                processed_match["loser_name"] = p2_name
                processed_match["winner_score"] = score1
                processed_match["loser_score"] = score2
            else:
                processed_match["winner_name"] = p2_name
                processed_match["loser_name"] = p1_name
                processed_match["winner_score"] = score2
                processed_match["loser_score"] = score1

        processed_matches.append(processed_match)

    return processed_matches


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

    latest_matches = get_latest_matches()

    return render_template(
        "leaderboard.html",
        players=players,
        latest_matches=latest_matches,
        current_user_id=g.user["uid"],
    )
