"""Routes for the match blueprint."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from firebase_admin import firestore
from flask import (
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

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

    # GET logic to fetch player/team names for the UI...
    m_dict = cast("dict[str, Any]", match_data)
    match_type = m_dict.get("matchType", "singles")
    player1_name, player2_name = "Player 1", "Player 2"

    if match_type == "doubles":
        team1_id, team2_id = m_dict.get("team1Id"), m_dict.get("team2Id")
        if team1_id and team2_id:
            player1_name, player2_name = MatchService.get_team_names(db, team1_id, team2_id)
    else:
        p1_ref, p2_ref = m_dict.get("player1Ref"), m_dict.get("player2Ref")
        uids = [ref.id for ref in [p1_ref, p2_ref] if ref]
        names = MatchService.get_player_names(db, uids)
        if p1_ref: player1_name = names.get(p1_ref.id, "Player 1")
        if p2_ref: player2_name = names.get(p2_ref.id, "Player 2")

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
    db: Any, form: MatchForm, user_id: str, group_id: str | None, t_id: str | None
) -> None:
    """Populate player choices for the match form."""
    p1_cands = MatchService.get_candidate_player_ids(db, user_id, group_id, t_id, True)
    other_cands = MatchService.get_candidate_player_ids(db, user_id, group_id, t_id)
    all_uids = p1_cands | other_cands
    all_names = {}
    if all_uids:
        refs = [db.collection("users").document(uid) for uid in all_uids]
        for doc in db.get_all(refs):
            if doc.exists:
                all_names[doc.id] = doc.to_dict().get("name", doc.id)

    form.player1.choices = cast(Any, [(u, str(all_names.get(u, u))) for u in p1_cands])
    others = [(u, str(all_names.get(u, u))) for u in other_cands]
    form.player2.choices = form.partner.choices = form.opponent2.choices = cast(Any, others)


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
        data["group_id"] = data.get("group_id") or group_id
        data["tournament_id"] = data.get("tournament_id") or t_id

        try:
            from .models import MatchSubmission

            # Using structured submission to ensure backend consistency
            submission = MatchSubmission(
                player_1_id=data["player1"],
                player_2_id=data["player2"],
                score_p1=data["player1_score"],
                score_p2=data["player2_score"],
                match_type=data["match_type"],
                match_date=data["match_date"],
                partner_id=data.get("partner"),
                opponent_2_id=data.get("opponent2"),
                group_id=data.get("group_id"),
                tournament_id=data.get("tournament_id"),
            )
            result = MatchService.record_match(db, submission, g.user)

            m_id = result.id
            if request.is_json:
                return jsonify({"status": "success", "match_id": m_id}), 200

            flash("Match recorded successfully.", "success")

            # Prioritize redirects: Tournament -> Group -> Summary
            if tid := data.get("tournament_id"):
                return redirect(url_for("tournament.view_tournament", tournament_id=tid))
            if gid := data.get("group_id"):
                return redirect(url_for("group.view_group", group_id=gid))

            return redirect(url_for("match.view_match_summary", match_id=m_id))

        except Exception as e:
            if request.is_json:
                return jsonify({"status": "error", "message": str(e)}), 400
            flash(str(e), "danger")

    return render_template("record_match.html", form=form, group_id=group_id, tournament_id=t_id)