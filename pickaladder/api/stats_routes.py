"""API routes for dashboard statistics."""

from __future__ import annotations

from firebase_admin import firestore
from flask import Blueprint, Response, g, jsonify, render_template

from pickaladder.auth.decorators import login_required
from pickaladder.core.activity.services import ActivityService
from pickaladder.user.services.dashboard import (
    _fetch_recent_activity,
    _fetch_vanity_stats,
)

bp = Blueprint("api_stats", __name__, url_prefix="/api/stats")


@bp.route("/vanity_metrics")
@login_required
def vanity_metrics() -> str:
    """Return vanity metrics HTML fragment."""
    db = firestore.client()
    user_id = g.user.uid
    user_data, vanity_metrics = _fetch_vanity_stats(db, user_id)

    return render_template(
        "components/_vanity_stats.html",
        stats=vanity_metrics,
        current_streak=vanity_metrics.get("current_streak", 0),
        user=user_data,
    )


@bp.route("/recent_matches")
@login_required
def recent_matches() -> str:
    """Return recent matches HTML fragment."""
    db = firestore.client()
    user_id = g.user.uid
    activity = _fetch_recent_activity(db, user_id)

    return render_template(
        "components/_recent_matches.html",
        matches=activity["matches"],
        next_cursor=activity["next_cursor"],
        user=g.user,
    )


@bp.route("/activity/<string:activity_id>/react", methods=["POST"])
@login_required
def react_to_activity(activity_id: str) -> Response:
    """Toggle reaction on an activity."""
    db = firestore.client()
    user_id = g.user.uid

    reactions = ActivityService.toggle_reaction(db, activity_id, user_id)

    return jsonify(
        {
            "status": "success",
            "count": len(reactions),
            "user_reacted": any(r["userId"] == user_id for r in reactions),
        }
    )
