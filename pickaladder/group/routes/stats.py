"""Stats routes for the group blueprint."""

from __future__ import annotations

from firebase_admin import firestore
from flask import flash, g, redirect, render_template, request, url_for

from pickaladder.auth.decorators import login_required
from pickaladder.constants.messages import GROUP_MESSAGES
from pickaladder.group import bp
from pickaladder.group.services.leaderboard import get_leaderboard_trend_data
from pickaladder.group.services.stats import get_head_to_head_stats
from pickaladder.group.utils import get_user_group_stats


@bp.route("/<string:group_id>/leaderboard-trend")
@login_required
def view_leaderboard_trend(group_id: str) -> Response | str | dict[str, object]:
    """Display a trend chart of the group's leaderboard."""
    db = firestore.client()
    group_ref = db.collection("groups").document(group_id)
    group = group_ref.get()
    if not group.exists:
        flash(GROUP_MESSAGES["NOT_FOUND"], "danger")
        return redirect(url_for(".view_groups"))

    group_data = group.to_dict() or {}
    group_data["id"] = group.id

    trend_data = get_leaderboard_trend_data(group_id)
    user_stats = get_user_group_stats(group_id, g.user.uid)

    return render_template(
        "group_leaderboard_trend.html",
        group=group_data,
        trend_data=trend_data,
        user_stats=user_stats,
    )


@bp.route("/<string:group_id>/stats/rivalry", methods=["GET"])
@login_required
def get_rivalry_stats(group_id: str) -> Response | str | dict[str, object]:
    """Return head-to-head stats for two players in a group."""
    playerA_id = request.args.get("playerA_id")
    playerB_id = request.args.get("playerB_id")

    if not playerA_id or not playerB_id:
        return {"error": "playerA_id and playerB_id are required"}, 400

    stats = get_head_to_head_stats(group_id, playerA_id, playerB_id)

    return {
        "wins": stats["wins"],
        "losses": stats["losses"],
        "matches": stats["matches"],
        "point_diff": stats["point_diff"],
        "avg_points_scored": stats["avg_points_scored"],
        "partnership_record": stats["partnership_record"],
    }


@bp.route("/<string:group_id>/user-trend/<string:user_id>")
@login_required
def get_user_group_trend(
    group_id: str,
    user_id: str,
) -> Response | str | dict[str, object]:
    """Return trend data for a specific user in a group."""
    trend_data = get_leaderboard_trend_data(group_id)

    # Filter for the specific user
    user_dataset = next(
        (ds for ds in trend_data["datasets"] if ds.get("id") == user_id),
        None,
    )

    if not user_dataset:
        return {"error": "User data not found for this group"}, 404

    return {
        "labels": trend_data["labels"],
        "dataset": user_dataset,
    }
