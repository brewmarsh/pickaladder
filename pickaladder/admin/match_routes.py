"""Match management routes."""

from typing import Any

from firebase_admin import firestore
from flask import Response, flash, g, jsonify, redirect, render_template, url_for

from pickaladder.admin import bp
from pickaladder.admin.services import AdminService
from pickaladder.auth.decorators import login_required
from pickaladder.constants.messages import ADMIN_MESSAGES, COMMON_MESSAGES


@bp.route("/matches")
@login_required(admin_required=True)
def admin_matches() -> str:
    """Display a list of all matches."""
    db = firestore.client()
    try:
        matches = (
            db.collection("matches")
            .order_by("createdAt", direction=firestore.Query.DESCENDING)
            .limit(50)
            .stream()
        )
    except KeyError:
        matches = db.collection("matches").limit(50).stream()
    return render_template("admin/matches.html", matches=matches)


@bp.route("/delete_match/<string:match_id>", methods=["POST"])
@login_required(admin_required=True)
def admin_delete_match(match_id: str) -> Any:
    """Delete a match document from Firestore."""
    db = firestore.client()
    try:
        db.collection("matches").document(match_id).delete()
        AdminService.log_action(db, g.user.uid, match_id, "delete_match")
        flash(ADMIN_MESSAGES["MATCH_DELETE_SUCCESS"], "success")
    except Exception as e:
        flash(COMMON_MESSAGES["GENERIC_ERROR"].format(error=e), "danger")
    return redirect(url_for(".admin_matches"))


@bp.route("/friend_graph_data")
@login_required(admin_required=True)
def friend_graph_data() -> Response | tuple[Response, int]:
    """Provide data for a network graph of users and their friendships."""
    try:
        return jsonify(AdminService.build_friend_graph(firestore.client()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500
