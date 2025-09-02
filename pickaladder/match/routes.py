import uuid
from datetime import date
from flask import render_template, request, redirect, url_for, session, flash
from sqlalchemy import or_, case, func
from pickaladder import db
from . import bp
from .forms import MatchForm
from pickaladder.models import Match, User
from pickaladder.errors import ValidationError
from pickaladder.constants import USER_ID


def get_player_record(player_id):
    """Calculates the win/loss record for a given player."""
    wins = (
        db.session.query(func.count(Match.id))
        .filter(
            or_(
                (Match.player1_id == player_id)
                & (Match.player1_score > Match.player2_score),
                (Match.player2_id == player_id)
                & (Match.player2_score > Match.player1_score),
            )
        )
        .scalar()
    )

    losses = (
        db.session.query(func.count(Match.id))
        .filter(
            or_(
                (Match.player1_id == player_id)
                & (Match.player1_score < Match.player2_score),
                (Match.player2_id == player_id)
                & (Match.player2_score < Match.player1_score),
            )
        )
        .scalar()
    )

    return {"wins": wins, "losses": losses}


@bp.route("/<uuid:match_id>")
def view_match_page(match_id):
    if USER_ID not in session:
        return redirect(url_for("auth.login"))

    match = Match.query.get_or_404(match_id)
    player1_record = get_player_record(match.player1_id)
    player2_record = get_player_record(match.player2_id)

    return render_template(
        "view_match.html",
        match=match,
        player1_record=player1_record,
        player2_record=player2_record,
    )


@bp.route("/create", methods=["GET", "POST"])
def create_match():
    if User.query.filter_by(is_admin=True).first() is None:
        return redirect(url_for("auth.install"))
    if USER_ID not in session:
        return redirect(url_for("auth.login"))

    user_id = uuid.UUID(session[USER_ID])
    user = User.query.get(user_id)
    form = MatchForm()

    # Get user's accepted friends for the opponent dropdown
    friend_ids = [
        f.friend_id for f in user.friend_requests_sent if f.status == "accepted"
    ]
    friends = User.query.filter(User.id.in_(friend_ids)).all()
    form.player2.choices = [(str(f.id), f.name) for f in friends]

    pre_selected_opponent_id = request.args.get("opponent_id")
    if pre_selected_opponent_id and request.method == 'GET':
        form.player2.data = pre_selected_opponent_id

    if form.validate_on_submit():
        try:
            new_match = Match(
                player1_id=user_id,
                player2_id=uuid.UUID(form.player2.data),
                player1_score=form.player1_score.data,
                player2_score=form.player2_score.data,
                match_date=form.match_date.data,
            )
            db.session.add(new_match)
            db.session.commit()
            flash("Match created successfully.", "success")
            return redirect(url_for("user.dashboard"))
        except Exception as e:
            db.session.rollback()
            flash(f"An unexpected error occurred: {e}", "danger")

    return render_template(
        "create_match.html",
        form=form,
    )


@bp.route("/leaderboard")
def leaderboard():
    if USER_ID not in session:
        return redirect(url_for("auth.login"))

    try:
        # Define the case for player scores
        player_score = case(
            (Match.player1_id == User.id, Match.player1_score),
            else_=Match.player2_score,
        )

        # Query to get leaderboard data
        players = (
            db.session.query(
                User.id,
                User.name,
                func.avg(player_score).label("avg_score"),
                func.count(Match.id).label("games_played"),
            )
            .join(Match, or_(User.id == Match.player1_id, User.id == Match.player2_id))
            .group_by(User.id, User.name)
            .order_by(func.avg(player_score).desc())
            .limit(10)
            .all()
        )

    except Exception as e:
        players = []
        flash(f"An error occurred while fetching the leaderboard: {e}", "danger")

    current_user_id = uuid.UUID(session[USER_ID])
    return render_template(
        "leaderboard.html", players=players, current_user_id=current_user_id
    )
