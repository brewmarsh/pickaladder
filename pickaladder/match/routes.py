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

# ... (edit_match and view_match_summary remain unchanged)

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
        submission = MatchSubmission(
            match_type=data["match_type"],
            player_1_id=data["player1"],
            player_2_id=data["player2"],
            score_p1=data["player1_score"],
            score_p2=data["player2_score"],
            match_date=data["match_date"],
            partner_id=data.get("partner"),
            opponent_2_id=data.get("opponent2"),
            group_id=data.get("group_id") or group_id,
            tournament_id=data.get("tournament_id") or t_id,
        )
        try:
            result = MatchService.record_match(db, submission, g.user)
            if request.is_json:
                return jsonify({"status": "success", "match_id": result.id}), 200
            
            flash("Match recorded successfully.", "success")
            
            # RESOLVED: Using object-based redirect logic from main branch
            if tid := submission.tournament_id:
                return redirect(url_for("tournament.view_tournament", tournament_id=tid))
            if gid := submission.group_id:
                return redirect(url_for("group.view_group", group_id=gid))
            
            return redirect(url_for("match.view_match_summary", match_id=result.id))
        except Exception as e:
            if request.is_json:
                return jsonify({"status": "error", "message": str(e)}), 400
            flash(str(e), "danger")

    # ... (remaining GET rendering logic remains unchanged)