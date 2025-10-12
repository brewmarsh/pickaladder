from flask import render_template, redirect, url_for, flash, g
from firebase_admin import firestore
import datetime

from . import bp
from .forms import MatchForm
from pickaladder.auth.decorators import login_required

def get_player_record(player_ref):
    """Calculates the win/loss record for a given player by their document reference."""
    db = firestore.client()
    wins = 0
    losses = 0

    # Matches where the user is player1
    p1_matches_query = db.collection("matches").where("player1Ref", "==", player_ref).stream()
    for match in p1_matches_query:
        data = match.to_dict()
        if data.get("player1Score", 0) > data.get("player2Score", 0):
            wins += 1
        else:
            losses += 1

    # Matches where the user is player2
    p2_matches_query = db.collection("matches").where("player2Ref", "==", player_ref).stream()
    for match in p2_matches_query:
        data = match.to_dict()
        if data.get("player2Score", 0) > data.get("player1Score", 0):
            wins += 1
        else:
            losses += 1

    return {"wins": wins, "losses": losses}

@bp.route("/<string:match_id>")
@login_required
def view_match_page(match_id):
    """Displays the details of a single match."""
    db = firestore.client()
    match_ref = db.collection("matches").document(match_id)
    match = match_ref.get()
    if not match.exists:
        flash("Match not found.", "danger")
        return redirect(url_for("user.dashboard"))

    match_data = match.to_dict()

    # Fetch player data from references
    player1 = match_data["player1Ref"].get()
    player2 = match_data["player2Ref"].get()

    player1_record = get_player_record(match_data["player1Ref"])
    player2_record = get_player_record(match_data["player2Ref"])

    return render_template(
        "view_match.html",
        match=match_data,
        player1=player1.to_dict(),
        player2=player2.to_dict(),
        player1_record=player1_record,
        player2_record=player2_record,
    )

@bp.route("/create", methods=["GET", "POST"])
@login_required
def create_match():
    db = firestore.client()
    user_id = g.user["uid"]
    form = MatchForm()

    # Populate opponent choices from the user's friends
    friends_ref = db.collection("users").document(user_id).collection("friends")
    accepted_friends_docs = friends_ref.where("status", "==", "accepted").stream()
    friend_ids = [doc.id for doc in accepted_friends_docs]

    if friend_ids:
        friends = db.collection("users").where("__name__", "in", friend_ids).stream()
        form.player2.choices = [(doc.id, doc.to_dict().get("name", doc.id)) for doc in friends]
    else:
        form.player2.choices = []

    if form.validate_on_submit():
        try:
            player1_ref = db.collection("users").document(user_id)
            player2_ref = db.collection("users").document(form.player2.data)

            db.collection("matches").add({
                "player1Ref": player1_ref,
                "player2Ref": player2_ref,
                "player1Score": form.player1_score.data,
                "player2Score": form.player2_score.data,
                "matchDate": form.match_date.data or datetime.date.today(),
                "createdAt": firestore.SERVER_TIMESTAMP,
            })
            flash("Match created successfully.", "success")
            return redirect(url_for("user.dashboard"))
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")

    return render_template("create_match.html", form=form)


@bp.route("/leaderboard")
@login_required
def leaderboard():
    """
    Displays a global leaderboard.
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

            players.append({
                "id": user.id,
                "name": user_data.get("name", "N/A"),
                "wins": record["wins"],
                "losses": record["losses"],
                "games_played": games_played,
                "win_percentage": win_percentage,
            })

        # Sort players by win percentage, then by wins
        players.sort(key=lambda p: (p["win_percentage"], p["wins"]), reverse=True)

    except Exception as e:
        players = []
        flash(f"An error occurred while fetching the leaderboard: {e}", "danger")

    return render_template("leaderboard.html", players=players, current_user_id=g.user["uid"])