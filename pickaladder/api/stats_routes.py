"""API routes for dashboard statistics."""

from __future__ import annotations

from typing import Any

from firebase_admin import firestore
from flask import Blueprint, g, render_template

from pickaladder.auth.decorators import login_required
from pickaladder.user.services.dashboard import (
    _fetch_recent_activity,
    _fetch_vanity_stats,
)

bp = Blueprint("api_stats", __name__, url_prefix="/api/stats")


@bp.route("/vanity_metrics")
@login_required
def vanity_metrics() -> Any:
    """Return vanity metrics HTML fragment."""
    db = firestore.client()
    user_id = g.user["uid"]
    user_data, vanity_metrics = _fetch_vanity_stats(db, user_id)

    # We also need current_streak from recent activity for the vanity stats card
    activity = _fetch_recent_activity(db, user_id)

    return render_template(
        "components/_vanity_stats.html",
        stats=vanity_metrics,
        current_streak=activity["current_streak"],
        user=user_data,
    )


@bp.route("/recent_matches")
@login_required
def recent_matches() -> Any:
    """Return recent matches HTML fragment."""
    db = firestore.client()
    user_id = g.user["uid"]
    activity = _fetch_recent_activity(db, user_id)

    return render_template(
        "components/_recent_matches.html",
        matches=activity["matches"],
        next_cursor=activity["next_cursor"],
        user=g.user,
    )
