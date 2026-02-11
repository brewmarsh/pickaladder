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
@bp.route("/<string:match_id>")
@login_required
def view_match_page(match_id: str) -> Any:
    """Display the details of a single match."""
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
        # team1 and team2 are lists of refs
        team1_refs = m_dict.get("team1", [])
        team2_refs = m_dict.get("team2", [])

        team1_data = []
        for ref in team1_refs:
            p = ref.get()
            if p.exists:
                p_data = p.to_dict()
                p_data["id"] = p.id
                team1_data.append(p_data)

        team2_data = []
        for ref in team2_refs:
            p = ref.get()
            if p.exists:
                p_data = p.to_dict()
                p_data["id"] = p.id
                team2_data.append(p_data)

        context["team1"] = team1_data
        context["team2"] = team2_data

    else:
        # Fetch player data from references
        # Handle cases where refs might be missing in corrupted data
        player1_ref = m_dict.get("player1Ref")
        player2_ref = m_dict.get("player2Ref")

        player1_data = {}
        player2_data = {}
        player1_record = {"wins": 0, "losses": 0}
        player2_record = {"wins": 0, "losses": 0}

        if player1_ref:
            player1 = player1_ref.get()
            if player1.exists:
                player1_data = player1.to_dict()
                player1_data["id"] = player1.id
                player1_record = MatchService.get_player_record(db, player1_ref)

        if player2_ref:
            player2 = player2_ref.get()
            if player2.exists:
                player2_data = player2.to_dict()
                player2_data["id"] = player2.id
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
@bp.route("/summary/<string:match_id>")
@login_required
def view_match_summary(match_id: str) -> Any:
    """Display a summary of a match."""
    db = firestore.client()
    match_data = MatchService.get_match_by_id(db, match_id)
    if match_data is None:
        flash("Match not found.", "danger")
        return redirect(url_for("user.dashboard"))

    m_dict = cast("dict[str, Any]", match_data)
    match_type = m_dict.get("matchType", "singles")
    p1_score = m_dict.get("player1Score", 0)
    p2_score = m_dict.get("player2Score", 0)
    current_user_id = g.user["uid"]

    context: dict[str, Any] = {"match": match_data, "match_type": match_type}

    if match_type == "doubles":
        team1_refs = m_dict.get("team1", [])
        team2_refs = m_dict.get("team2", [])

        team1_data = [d.to_dict() for d in db.get_all(team1_refs) if d.exists]
        team2_data = [d.to_dict() for d in db.get_all(team2_refs) if d.exists]

        if p1_score > p2_score:
            context["winners"] = team1_data
            context["losers"] = team2_data
        else:
            context["winners"] = team2_data
            context["losers"] = team1_data

        # Determine opponent_id for rematch
        # (target the team that doesn't contain the user)
        team1_ids = [ref.id for ref in team1_refs]
        if current_user_id in team1_ids:
            context["opponent_id"] = team2_refs[0].id if team2_refs else None
        else:
            context["opponent_id"] = team1_refs[0].id if team1_refs else None
    else:
        player1_ref = m_dict.get("player1Ref")
        player2_ref = m_dict.get("player2Ref")

        refs = [r for r in [player1_ref, player2_ref] if r]
        docs = {d.id: d.to_dict() for d in db.get_all(refs) if d.exists}

        player1_data = docs.get(player1_ref.id) if player1_ref else {}
        player2_data = docs.get(player2_ref.id) if player2_ref else {}

        if p1_score > p2_score:
            context["winners"] = [player1_data]
            context["losers"] = [player2_data]
        else:
            context["winners"] = [player2_data]
            context["losers"] = [player1_data]

        # Determine opponent_id for rematch
        if player1_ref and player1_ref.id == current_user_id:
            context["opponent_id"] = player2_ref.id if player2_ref else None
        else:
            context["opponent_id"] = player1_ref.id if player1_ref else None

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

        # Support pre-populating multiple players (Rematch logic from Main)
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

    if form.validate_on_submit():
        # Ensure group_id and tournament_id from request args are preserved
        # if not in form data, especially relevant for JSON submissions.
        data = form.data
        if not data.get("group_id"):
            data["group_id"] = group_id
        if not data.get("tournament_id"):
            data["tournament_id"] = tournament_id

        try:
            # Capture the ID from the service call (Feature Branch Logic)
            match_id = MatchService.process_match_submission(db, user_id, form)

            if request.is_json:
                return jsonify({
                    "status": "success",
                    "message": "Match recorded.",
                    "match_id": match_id
                }), 200

            flash("Match recorded successfully.", "success")
            active_tid = form.tournament_id.data or tournament_id
            active_gid = form.group_id.data or group_id

            if active_tid:
                return redirect(
                    url_for("tournament.view_tournament", tournament_id=active_tid)
                )
            if active_gid:
                return redirect(url_for("group.view_group", group_id=active_gid))

            # Redirect to the new summary view (Feature Branch Logic)
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
        players = MatchService.get_leaderboard_data(db)
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