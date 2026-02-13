"""Routes for the match blueprint."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from firebase_admin import firestore
from flask import flash, g, jsonify, redirect, render_template, request, url_for

from pickaladder.auth.decorators import login_required

from . import bp
from .forms import MatchForm
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
        if team1_id:
            t1_doc = db.collection("teams").document(team1_id).get()
            if t1_doc.exists:
                player1_name = t1_doc.to_dict().get("name", "Team 1")
        if team2_id:
            t2_doc = db.collection("teams").document(team2_id).get()
            if t2_doc.exists:
                player2_name = t2_doc.to_dict().get("name", "Team 2")
    else:
        p1_ref = m_dict.get("player1Ref")
        p2_ref = m_dict.get("player2Ref")
        if p1_ref:
            p1_doc = p1_ref.get()
            if p1_doc.exists:
                player1_name = p1_doc.to_dict().get("name", "Player 1")
        if p2_ref:
            p2_doc = p2_ref.get()
            if p2_doc.exists:
                player2_name = p2_doc.to_dict().get("name", "Player 2")

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
    match_data = MatchService.get_match_by_id(db, match_id)
    if match_data is None:
        flash("Match not found.", "danger")
        return redirect(url_for("user.dashboard"))

    # Cast to dict to avoid mypy Mapping.get issues with TypedDict
    m_dict = cast("dict[str, Any]", match_data)
    match_type = m_dict.get("matchType", "singles")

    context = {"match": match_data, "match_type": match_type}

    if match_type == "doubles":
        # Fetch team members
        team1_refs = m_dict.get("team1", [])
        team2_refs = m_dict.get("team2", [])

        team1_data = []
        if team1_refs:
            for doc in db.get_all(team1_refs):
                if doc.exists:
                    p_data = doc.to_dict()
                    p_data["id"] = doc.id
                    team1_data.append(p_data)

        team2_data = []
        if team2_refs:
            for doc in db.get_all(team2_refs):
                if doc.exists:
                    p_data = doc.to_dict()
                    p_data["id"] = doc.id
                    team2_data.append(p_data)

        context["team1"] = team1_data
        context["team2"] = team2_data

    else:
        # Fetch player data from references
        player1_ref = m_dict.get("player1Ref")
        player2_ref = m_dict.get("player2Ref")

        player1_data = {}
        player2_data = {}
        player1_record = {"wins": 0, "losses": 0}
        player2_record = {"wins": 0, "losses": 0}

        if player1_ref:
            p1_doc = player1_ref.get()
            if p1_doc.exists:
                player1_data = p1_doc.to_dict()
                player1_data["id"] = p1_doc.id
                player1_record = MatchService.get_player_record(db, player1_ref)

        if player2_ref:
            p2_doc = player2_ref.get()
            if p2_doc.exists:
                player2_data = p2_doc.to_dict()
                player2_data["id"] = p2_doc.id
                player2_record = MatchService.get_player_record(db, player2_ref)

        context.update(
            {
                "player1": player1_data,
                "player2": player2_data,
                "player1_record": player1_record,
                "player2_record": player2_record,
            }
        )

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
    if request.is_json:
        form = MatchForm(data=request.get_json())
    else:
        form = MatchForm()

    # Populate choices for validation and UI
    p1_candidates = MatchService.get_candidate_player_ids(
        db, user_id, group_id, tournament_id, include_user=True
    )
    other_candidates = MatchService.get_candidate_player_ids(
        db, user_id, group_id, tournament_id
    )

    all_uids = p1_candidates | other_candidates
    all_names = {}
    if all_uids:
        candidate_refs = [db.collection("users").document(uid) for uid in all_uids]
        for doc in db.get_all(candidate_refs):
            if doc.exists:
                all_names[doc.id] = doc.to_dict().get("name", doc.id)

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
            user_doc = db.collection("users").document(user_id).get()
            if user_doc.exists:
                form.match_type.data = user_doc.to_dict().get(
                    "lastMatchRecordedType", "singles"
                )

    if (request.method == "POST" or request.is_json) and form.validate():
        # Ensure group_id and tournament_id from request args are preserved
        # if not in form data, especially relevant for JSON submissions.
        data = form.data
        if not data.get("group_id"):
            data["group_id"] = group_id
        if not data.get("tournament_id"):
            data["tournament_id"] = tournament_id

        try:
            # Capture the ID from the service call (Feature Branch Logic)
            match_id = MatchService.process_match_submission(db, data, g.user)

            if request.is_json:
                return jsonify(
                    {
                        "status": "success",
                        "message": "Match recorded.",
                        "match_id": match_id,
                    }
                ), 200

            flash("Match recorded successfully.", "success")
            if data.get("tournament_id"):
                return redirect(
                    url_for(
                        "tournament.view_tournament",
                        tournament_id=data["tournament_id"],
                    )
                )
            if data.get("group_id"):
                return redirect(url_for("group.view_group", group_id=data["group_id"]))
            return redirect(url_for("match.view_match_summary", match_id=match_id))
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
        t_doc = db.collection("tournaments").document(tournament_id).get()
        if t_doc.exists:
            tournament_name = t_doc.to_dict().get("name")

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
