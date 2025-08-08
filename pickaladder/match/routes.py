import uuid
from datetime import date
from flask import render_template, request, redirect, url_for, session, flash
from sqlalchemy import or_, case, func
from pydantic import BaseModel, validator, ValidationError as PydanticValidationError

from pickaladder import db
from . import bp
from pickaladder.models import Match, User
from pickaladder.errors import ValidationError
from pickaladder.constants import USER_ID


class MatchCreateSchema(BaseModel):
    player2_id: uuid.UUID
    player1_score: int
    player2_score: int
    match_date: date

    @validator("player1_score", "player2_score")
    def scores_must_be_positive(cls, v):
        if v < 0:
            raise ValueError("Scores cannot be negative.")
        return v

    @validator("player2_score")
    def scores_cannot_be_the_same(cls, v, values):
        if "player1_score" in values and v == values["player1_score"]:
            raise ValueError("Scores cannot be the same.")
        return v

    @validator("player2_score")
    def winner_must_have_11_points_and_win_by_2(cls, v, values):
        if "player1_score" in values:
            p1_score = values["player1_score"]
            p2_score = v
            if max(p1_score, p2_score) < 11:
                raise ValueError("One player must have at least 11 points to win.")
            if abs(p1_score - p2_score) < 2:
                raise ValueError("The winner must win by at least 2 points.")
        return v


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
    if USER_ID not in session:
        return redirect(url_for("auth.login"))

    user_id = uuid.UUID(session[USER_ID])
    user = User.query.get(user_id)

    # Get user's accepted friends for the opponent dropdown
    friend_ids = [
        f.friend_id for f in user.friend_requests_sent if f.status == "accepted"
    ]
    friends = User.query.filter(User.id.in_(friend_ids)).all()

    pre_selected_opponent_id = request.args.get("opponent_id", type=uuid.UUID)

    if request.method == "POST":
        try:
            form_data = {
                "player2_id": request.form.get("player2"),
                "player1_score": request.form.get("player1_score"),
                "player2_score": request.form.get("player2_score"),
                "match_date": request.form.get("match_date"),
            }
            validated_data = MatchCreateSchema(**form_data)

            new_match = Match(
                player1_id=user_id,
                player2_id=validated_data.player2_id,
                player1_score=validated_data.player1_score,
                player2_score=validated_data.player2_score,
                match_date=validated_data.match_date,
            )
            db.session.add(new_match)
            db.session.commit()
            flash("Match created successfully.", "success")
            return redirect(url_for("user.dashboard"))

        except PydanticValidationError as e:
            # Pydantic gives detailed errors, we can pass them to the user
            # For now, we'll just show the first error message.
            error_message = e.errors()[0]["msg"]
            raise ValidationError(error_message)
        except Exception as e:
            db.session.rollback()
            flash(f"An unexpected error occurred: {e}", "danger")
            return redirect(url_for(".create_match"))

    return render_template(
        "create_match.html",
        friends=friends,
        pre_selected_opponent_id=pre_selected_opponent_id,
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
