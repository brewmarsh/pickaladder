"""Routes for the match blueprint."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from firebase_admin import firestore
from flask import flash, g, jsonify, redirect, render_template, request, url_for

from pickaladder.auth.decorators import login_required

from . import bp
from .forms import MatchForm
from .models import MatchSubmission
from .services import MatchService

if TYPE_CHECKING:
    pass


# TODO: Add type hints for Agent clarity
@bp.route("/edit/<string:match_id>", methods=["GET", "POST"])
@login_required
def edit_match(match_id: str) -> Any:
    """Edit an existing match's scores."""
    db = firestore.client()
    match_data = MatchService.get_match_by_id(db, match_id)
    if match_data is None:
        flash("Match not found.", "danger")
        return redirect(url_for("user.dashboard"))

    if request.method == "POST":
        try:
            new_p1_score = int(request.form.get("player1_score", 0))
            new_p2_score = int(request.form.get("player2_score", 0))

            MatchService.update_match_score(
                db, match_id, new_p1_score, new_p2_score, g.user["uid"]
            )
            flash("Match updated successfully.", "success")
            return redirect(url_for("match.view_match_summary", match_id=match_id))
        except PermissionError as e:
            flash(str(e), "danger")
        except ValueError as e:
            flash(str(e), "danger")
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")

    # For GET or on error, render the edit page
    # Fetch player names for the UI
    m_dict = cast("dict[str, Any]", match_data)
    match_type = m_dict.get("matchType", "singles")
    player1_name = "Player 1"
    player2_name = "Player 2"

    if match_type == "doubles":
        team1_id = m_dict.get("team1Id")
        team2_id = m_dict.get("team2Id")
        if team1_id and team2_id:
            player1_name, player2_name = MatchService.get_team_names(
                db, team1_id, team2_id
            )
    else:
        p1_ref = m_dict.get("player1Ref")
        p2_ref = m_dict.get("player2Ref")
        uids = []
        if p1_ref:
            uids.append(p1_ref.id)
        if p2_ref:
            uids.append(p2_ref.id)
        names = MatchService.get_player_names(db, uids)
        if p1_ref:
            player1_name = names.get(p1_ref.id, "Player 1")
        if p2_ref:
            player2_name = names.get(p2_ref.id, "Player 2")

    return render_template(
        "match/edit_match.html",
        match=match_data,
        player1_name=player1_name,
        player2_name=player2_name,
        is_admin=g.user.get("isAdmin", False),
    )


@bp.route("/<string:match_id>")
@bp.route("/summary/<string:match_id>")
@login_required
def view_match_summary(match_id: str) -> Any:
    """Display the summary of a single match."""
    db = firestore.client()
    context = MatchService.get_match_summary_context(db, match_id)
    if not context:
        flash("Match not found.", "danger")
        return redirect(url_for("user.dashboard"))

    return render_template("match/summary.html", **context)


# TODO: Add type hints for Agent clarity
@bp.route("/record", methods=["GET", "POST"])
@login_required
def record_match() -> Any:
    """Handle match recording for both web form and optimistic JSON submission."""
    db = firestore.client()
    user_id = g.user["uid"]
    group_id = request.args.get("group_id")
    tournament_id = request.args.get("tournament_id")

    # JSON handling merged into form data
    form_data = request.get_json() if request.is_json else None
    form = MatchForm(data=form_data)

    # Populate choices for validation and UI
    p1_candidates = MatchService.get_candidate_player_ids(
        db, user_id, group_id, tournament_id, include_user=True
    )
    other_candidates = MatchService.get_candidate_player_ids(
        db, user_id, group_id, tournament_id
    )

    all_uids = p1_candidates | other_candidates
    all_names = MatchService.get_player_names(db, all_uids)

    form.player1.choices = [  # type: ignore[assignment]
        (uid, str(all_names.get(uid, uid))) for uid in p1_candidates
    ]
    other_choices = [(uid, str(all_names.get(uid, uid))) for uid in other_candidates]
    form.player2.choices = form.partner.choices = form.opponent2.choices = other_choices  # type: ignore[assignment]

    if request.method == "GET":
        form.player1.data = user_id
        form.group_id.data = group_id
        form.tournament_id.data = tournament_id

        # Support pre-populating multiple players (Rematch logic)
        match_type = request.args.get("match_type")
        if match_type:
            form.match_type.data = match_type

        p1 = request.args.get("player1")
        p2 = request.args.get("player2")
        p3 = request.args.get("player3")
        p4 = request.args.get("player4")

        if p1:
            form.player1.data = p1
        if p2:
            form.partner.data = p2
        if p3:
            form.player2.data = p3
        if p4:
            form.opponent2.data = p4

        # Backward compatibility for single opponent
        opponent_id = request.args.get("opponent") or request.args.get("opponent_id")
        if opponent_id and not p3:
            form.player2.data = opponent_id

        if not match_type:
            form.match_type.data = MatchService.get_user_last_match_type(db, user_id)

    if form.validate_on_submit():
        # Ensure group_id and tournament_id from request args are preserved
        # if not in form data, especially relevant for JSON submissions.
        data = form.data
        if not data.get("group_id"):
            data["group_id"] = group_id
        if not data.get("tournament_id"):
            data["tournament_id"] = tournament_id

        # Create MatchSubmission dataclass
        submission = MatchSubmission(
            player_1_id=data["player1"],
            player_2_id=data["player2"],
            score_p1=int(data["player1_score"]),
            score_p2=int(data["player2_score"]),
            match_type=data["match_type"],
            partner_id=data.get("partner"),
            opponent_2_id=data.get("opponent2"),
            group_id=data.get("group_id"),
            tournament_id=data.get("tournament_id"),
            match_date=data.get("match_date"),
            created_by=user_id,
        )

        try:
            # Explicit validation via dataclass
            submission.validate()

            # Record match via service
            result = MatchService.record_match(db, submission, g.user)
            match_id = result.id

            if request.is_json:
                return jsonify(
                    {
                        "status": "success",
                        "message": "Match recorded.",
                        "match_id": match_id,
                    }
                ), 200

            flash("Match recorded successfully.", "success")
            active_tid = submission.tournament_id or tournament_id
            active_gid = submission.group_id or group_id
            if active_tid:
                return redirect(
                    url_for("tournament.view_tournament", tournament_id=active_tid)
                )
            if active_gid:
                return redirect(url_for("group.view_group", group_id=active_gid))
            return redirect(url_for("user.dashboard"))
        except ValueError as e:
            if request.is_json:
                return jsonify({"status": "error", "message": str(e)}), 400
            flash(str(e), "danger")
        except Exception as e:
            if request.is_json:
                return jsonify({"status": "error", "message": str(e)}), 500
            flash(f"An unexpected error occurred: {e}", "danger")

    tournament_name = None
    if tournament_id:
        tournament_name = MatchService.get_tournament_name(db, tournament_id)

    return render_template(
        "record_match.html",
        form=form,
        group_id=group_id,
        tournament_id=tournament_id,
        tournament_name=tournament_name,
    )


# TODO: Add type hints for Agent clarity
@bp.route("/leaderboard")
@login_required
def leaderboard() -> Any:
    """Display a global leaderboard.

    Note: This is a simplified, non-scalable implementation. A production-ready
    leaderboard on Firestore would likely require denormalization and Cloud Functions.
    """
    db = firestore.client()
    try:
        # Exclude players with 0 games and sort by Win Percentage
        players = MatchService.get_leaderboard_data(db, min_games=1)
    except Exception as e:
        players = []
        flash(f"An error occurred while fetching the leaderboard: {e}", "danger")

    latest_matches = MatchService.get_latest_matches(db)

    return render_template(
        "leaderboard.html",
        players=players,
        latest_matches=latest_matches,
        current_user_id=g.user["uid"],
    )
