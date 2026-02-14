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
    from google.cloud.firestore_v1.client import Client


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


def _populate_match_form_choices(
    db: Client, form: MatchForm, user_id: str, group_id: str | None, t_id: str | None
) -> None:
    """Populate player choices for the match form."""
    p1_cands = MatchService.get_candidate_player_ids(db, user_id, group_id, t_id, True)
    other_cands = MatchService.get_candidate_player_ids(db, user_id, group_id, t_id)
    all_uids = p1_cands | other_cands
    all_names = {}
    if all_uids:
        refs = [db.collection("users").document(uid) for uid in all_uids]
        for doc in db.get_all(refs):
            d_snap = cast("firestore.DocumentSnapshot", doc)
            if d_snap.exists:
                all_names[d_snap.id] = (d_snap.to_dict() or {}).get("name", d_snap.id)

    form.player1.choices = [(u, str(all_names.get(u, u))) for u in p1_cands]
    others = [(u, str(all_names.get(u, u))) for u in other_cands]
    form.player2.choices = cast(Any, others)
    form.partner.choices = cast(Any, others)
    form.opponent2.choices = cast(Any, others)


def _handle_record_match_get(
    db: Client, form: MatchForm, user_id: str, group_id: str | None, t_id: str | None
) -> None:
    """Handle GET parameters for pre-populating the match form."""
    form.player1.data = user_id
    form.group_id.data = group_id
    form.tournament_id.data = t_id
    if match_type := request.args.get("match_type"):
        form.match_type.data = match_type
    if p1 := request.args.get("player1"):
        form.player1.data = p1
    if p2 := request.args.get("player2"):
        form.partner.data = p2
    if p3 := request.args.get("player3"):
        form.player2.data = p3
    if p4 := request.args.get("player4"):
        form.opponent2.data = p4
    opp_id = request.args.get("opponent") or request.args.get("opponent_id")
    if opp_id and not request.args.get("player3"):
        form.player2.data = opp_id
    if not form.match_type.data:
        u_doc = cast(
            "firestore.DocumentSnapshot", db.collection("users").document(user_id).get()
        )
        if u_doc.exists:
            u_dict = u_doc.to_dict() or {}
            form.match_type.data = u_dict.get("lastMatchRecordedType", "singles")


@bp.route("/record", methods=["GET", "POST"])
@login_required
def record_match() -> Any:
    """Handle match recording for both web form and optimistic JSON submission."""
    db, user_id = firestore.client(), g.user["uid"]
    group_id, t_id = request.args.get("group_id"), request.args.get("tournament_id")
    form = MatchForm(data=request.get_json() if request.is_json else None)

    _populate_match_form_choices(db, form, user_id, group_id, t_id)
    if request.method == "GET":
        _handle_record_match_get(db, form, user_id, group_id, t_id)

    if form.validate_on_submit():
        data = form.data
        try:
            submission = MatchSubmission(
                player_1_id=data["player1"],
                player_2_id=data["player2"],
                score_p1=data["player1_score"],
                score_p2=data["player2_score"],
                match_type=data["match_type"],
                match_date=data["match_date"],
                partner_id=data.get("partner"),
                opponent_2_id=data.get("opponent2"),
                group_id=data.get("group_id") or group_id,
                tournament_id=data.get("tournament_id") or t_id,
                created_by=user_id,
            )
            result = MatchService.record_match(db, submission, g.user)
            m_id = result.id

            if request.is_json:
                return jsonify({"status": "success", "match_id": m_id}), 200

            flash("Match recorded successfully.", "success")

            # Prioritize redirects: Tournament -> Group -> Summary
            if tid := submission.tournament_id:
                return redirect(
                    url_for("tournament.view_tournament", tournament_id=tid)
                )
            if gid := submission.group_id:
                return redirect(url_for("group.view_group", group_id=gid))

            return redirect(url_for("match.view_match_summary", match_id=m_id))
        except Exception as e:
            if request.is_json:
                return jsonify({"status": "error", "message": str(e)}), 400
            flash(str(e), "danger")

    t_name = None
    if t_id:
        t_doc = cast(
            "firestore.DocumentSnapshot",
            db.collection("tournaments").document(t_id).get(),
        )
        t_name = (t_doc.to_dict() or {}).get("name") if t_doc.exists else None

    return render_template(
        "record_match.html",
        form=form,
        group_id=group_id,
        tournament_id=t_id,
        tournament_name=t_name,
    )


# TODO: Add type hints for Agent clarity
@bp.route("/history")
@login_required
def get_match_history() -> Any:
    """Fetch paginated match history for the current user."""
    db = firestore.client()
    cursor = request.args.get("cursor")
    limit = request.args.get("limit", 20, type=int)
    uid = g.user["uid"]

    matches, next_cursor = MatchService.get_matches_for_user(db, uid, limit, cursor)

    return jsonify({"matches": matches, "next_cursor": next_cursor})


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
