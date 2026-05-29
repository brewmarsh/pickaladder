"""User JSON API routes for the user blueprint."""

from __future__ import annotations

from typing import TYPE_CHECKING

from firebase_admin import firestore
from flask import (
    Response,
    g,
    jsonify,
    request,
)

from pickaladder.auth.decorators import login_required
from pickaladder.services.feedback_service import FeedbackService

from .. import bp
from ..services import UserService

if TYPE_CHECKING:
    pass


@bp.route("/api/feedback", methods=["POST"])
@login_required
def submit_feedback() -> Response | tuple[Response, int]:
    """Submit user feedback."""
    data = request.json
    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    feedback_type = data.get("type")
    message = data.get("message")

    if not feedback_type or not message:
        return jsonify({"success": False, "error": "Missing type or message"}), 400

    valid_types = ["Bug", "Feature Request", "General"]
    if feedback_type not in valid_types:
        return jsonify({"success": False, "error": "Invalid feedback type"}), 400

    FeedbackService.submit_feedback(
        firestore.client(), g.user.uid, feedback_type, message
    )
    return jsonify({"success": True, "message": "Feedback submitted successfully"})


@bp.route("/api/dashboard")
@login_required
def api_dashboard() -> Response:
    """Provide dashboard data as JSON."""
    user_id = g.user.uid
    # The JSON API should probably still include everything for backwards compatibility
    # and because it's usually used by clients that expect a full payload.
    data = UserService.get_dashboard_data(
        firestore.client(), user_id, include_activity=True
    )
    streak = data["stats"]["current_streak"]
    s_type = data["stats"]["streak_type"]
    return jsonify(
        {
            "user": UserService.get_user_by_id(firestore.client(), user_id),
            "friends": data["friends"],
            "requests": data["requests"],
            "matches": [
                dict(m) if not isinstance(m, dict) else m for m in data["matches"]
            ],
            "next_cursor": data.get("next_cursor"),
            "group_rankings": data["group_rankings"],
            "stats": {
                "total_matches": data["stats"]["total_games"],
                "win_percentage": data["stats"]["win_rate"],
                "current_streak": f"{streak}{s_type}" if data["matches"] else "N/A",
            },
        }
    )


@bp.route("/api/create_invite", methods=["POST"])
@login_required
def create_invite() -> Response:
    """Generate a unique invite token."""
    token = UserService.create_invite_token(firestore.client(), g.user.uid)
    return jsonify({"token": token})


@bp.route("/api/save_fcm_token", methods=["POST"])
@login_required
def save_fcm_token() -> Response | tuple[Response, int]:
    """Save the user's FCM token for push notifications."""
    token = request.json.get("token")
    if not token:
        return jsonify({"success": False, "error": "No token provided"}), 400

    UserService.update_fcm_token(firestore.client(), g.user.uid, token)
    return jsonify({"success": True})


@bp.route("/api/search")
@login_required
def api_search_users() -> Response:
    """Search for users and return JSON."""
    search_term = request.args.get("q", "")
    results = UserService.search_users_json(firestore.client(), g.user.uid, search_term)
    return jsonify(results)
