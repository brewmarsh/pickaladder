"""Feedback management routes."""

from typing import Any

from firebase_admin import firestore
from flask import flash, g, redirect, render_template, request, url_for

from pickaladder.admin import bp
from pickaladder.admin.services import AdminService
from pickaladder.auth.decorators import login_required
from pickaladder.services.feedback_service import FeedbackService
from pickaladder.user import UserService


@bp.route("/feedback")
@login_required(admin_required=True)
def view_feedback() -> str:
    """Render the feedback management page."""
    db = firestore.client()
    feedback_list = FeedbackService.get_all_feedback(db)

    # Resolve user names
    for item in feedback_list:
        user_id = item.get("userId")
        if user_id:
            user = UserService.get_user_by_id(db, user_id)
            item["user_name"] = (
                UserService.smart_display_name(user) if user else "Unknown User"
            )
        else:
            item["user_name"] = "Anonymous"

    return render_template("admin/feedback.html", feedback_list=feedback_list)


@bp.route("/feedback/status", methods=["POST"])
@login_required(admin_required=True)
def update_feedback_status() -> Any:
    """Update feedback status."""
    feedback_id = request.form.get("feedback_id")
    status = request.form.get("status")

    if not feedback_id or not status:
        flash("Missing feedback ID or status", "danger")
        return redirect(url_for(".view_feedback"))

    db = firestore.client()
    if FeedbackService.update_feedback_status(db, feedback_id, status, g.user.uid):
        AdminService.log_action(
            db,
            g.user.uid,
            feedback_id,
            "update_feedback_status",
            {"status": status},
        )
        flash("Feedback status updated", "success")
    else:
        flash("Failed to update feedback status", "danger")

    return redirect(url_for(".view_feedback"))
