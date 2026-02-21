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
    from google.cloud.firestore_v1.client import Client


def _populate_match_form_choices(
    db: Any, form: MatchForm, user_id: str, group_id: str | None, t_id: str | None
) -> None:
    """Populate player choices for the match form using cast for type safety."""
    p1_cands = MatchService.get_candidate_player_ids(db, user_id, group_id, t_id, True)
    other_cands = MatchService.get_candidate_player_ids(db, user_id, group_id, t_id)
    all_uids = p1_cands | other_cands
    all_names = {}
    if all_uids:
        refs = [db.collection("users").document(uid) for uid in all_uids]
        for doc in db.get_all(refs):
            if doc.exists:
                all_names[doc.id] = doc.to_dict().get("name", doc.id)

    # RESOLVED: Using cast(Any, ...) from main branch for cleaner type handling
    form.player1.choices = cast(Any, [(u, str(all_names.get(u, u))) for u in p1_cands])
    others = [(u, str(all_names.get(u, u))) for u in other_cands]
    form.player2.choices = form.partner.choices = form.opponent2.choices = cast(
        Any, others
    )


def _handle_record_match_get(
    db: Any, form: MatchForm, user_id: str, group_id: str | None, t_id: str | None
) -> None:
    """Handle GET parameters for pre-populating the match form. Merged from main branch."""
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
        u_doc = db.collection("users").document(user_id).get()
        if u_doc.exists:
            form.match_type.data = u_doc.to_dict().get("lastMatchRecordedType", "singles")


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
            # MatchService returns a result object in the jules/main merged version
            result = MatchService.record_match(db, data, g.user)
            m_id = result.id if hasattr(result, 'id') else result
            
            if request.is_json:
                return jsonify({"status": "success", "match_id": m_id}), 200
            
            flash("Match recorded successfully.", "success")
            
            # RESOLVED: Context-aware redirection from jules branch
            if tid := data.get("tournament_id"):
                return redirect(url_for("tournament.view_tournament", tournament_id=tid))
            if gid := data.get("group_id"):
                return redirect(url_for("group.view_group", group_id=gid))
            
            return redirect(url_for("match.view_match_summary", match_id=m_id))
            
        except Exception as e:
            if request.is_json:
                return jsonify({"status": "error", "message": str(e)}), 400
            flash(str(e), "danger")

    t_name = None
    if t_id:
        t_doc = db.collection("tournaments").document(t_id).get()
        t_name = t_doc.to_dict().get("name") if t_doc.exists else None

    return render_template("record_match.html", form=form, group_id=group_id,
                           tournament_id=t_id, tournament_name=t_name)


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
    """Display a global leaderboard."""
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