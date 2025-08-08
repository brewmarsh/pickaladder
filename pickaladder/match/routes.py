import uuid
from flask import render_template, request, redirect, url_for, session, flash
from sqlalchemy import or_, case, func

from pickaladder import db
from . import bp
from pickaladder.models import Match, User, Friend
from pickaladder.errors import ValidationError
from pickaladder.constants import USER_ID


def get_player_record(player_id):
    """Calculates the win/loss record for a given player."""
    wins = db.session.query(func.count(Match.id)).filter(
        or_(
            (Match.player1_id == player_id) & (Match.player1_score > Match.player2_score),
            (Match.player2_id == player_id) & (Match.player2_score > Match.player1_score)
        )
    ).scalar()

    losses = db.session.query(func.count(Match.id)).filter(
        or_(
            (Match.player1_id == player_id) & (Match.player1_score < Match.player2_score),
            (Match.player2_id == player_id) & (Match.player2_score < Match.player1_score)
        )
    ).scalar()

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
    if USER_ID not in session:
        return redirect(url_for("auth.login"))

    user_id = uuid.UUID(session[USER_ID])
    user = User.query.get(user_id)

    # Get user's accepted friends for the opponent dropdown
    friend_ids = [f.friend_id for f in user.friend_requests_sent if f.status == 'accepted']
    friends = User.query.filter(User.id.in_(friend_ids)).all()

    if request.method == "POST":
        try:
            player2_id = request.form["player2"]
            player1_score = int(request.form["player1_score"])
            player2_score = int(request.form["player2_score"])
            match_date = request.form["match_date"]

            # --- Validation Logic ---
            if player1_score < 0 or player2_score < 0:
                raise ValidationError("Scores cannot be negative.")
            if player1_score == player2_score:
                raise ValidationError("Scores cannot be the same.")
            if max(player1_score, player2_score) < 11:
                raise ValidationError("One player must have at least 11 points to win.")
            if abs(player1_score - player2_score) < 2:
                raise ValidationError("The winner must win by at least 2 points.")
            # --- End Validation Logic ---

            new_match = Match(
                player1_id=user_id,
                player2_id=player2_id,
                player1_score=player1_score,
                player2_score=player2_score,
                match_date=match_date
            )
            db.session.add(new_match)
            db.session.commit()
            flash("Match created successfully.", "success")
            return redirect(url_for("user.dashboard"))

        except (ValueError, TypeError):
            raise ValidationError("Scores must be valid numbers.")
        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred while creating the match: {e}", "danger")
            return redirect(url_for(".create_match"))

    return render_template("create_match.html", friends=friends)


@bp.route("/leaderboard")
def leaderboard():
    if USER_ID not in session:
        return redirect(url_for("auth.login"))

    try:
        # Define the case for player scores
        player_score = case(
            (Match.player1_id == User.id, Match.player1_score),
            else_=Match.player2_score
        )

        # Query to get leaderboard data
        players = db.session.query(
            User.id,
            User.name,
            func.avg(player_score).label('avg_score'),
            func.count(Match.id).label('games_played')
        ).join(
            Match,
            or_(User.id == Match.player1_id, User.id == Match.player2_id)
        ).group_by(User.id, User.name).order_by(
            func.avg(player_score).desc()
        ).limit(10).all()

    except Exception as e:
        players = []
        flash(f"An error occurred while fetching the leaderboard: {e}", "danger")

    return render_template("leaderboard.html", players=players)
