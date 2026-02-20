"""Admin routes for the application."""

import datetime
import random
from typing import Union

from faker import Faker
from firebase_admin import auth, firestore
from flask import (
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.wrappers import Response

from pickaladder.auth.decorators import login_required
from pickaladder.match.models import MatchSubmission
from pickaladder.match.services import MatchService
from pickaladder.user import UserService
from pickaladder.user.models import UserSession

from . import bp
from .services import AdminService

MIN_USERS_FOR_MATCH_GENERATION = 2


@bp.route("/")
@login_required(admin_required=True)
def admin() -> Union[str, Response]:
    """Render the main admin dashboard."""
    # Authorization check ensures only real admins (or those impersonating) gain access
    if not g.user or (not g.user.get("isAdmin") and not g.get("is_impersonating")):
        flash("You are not authorized to view this page.", "danger")
        return redirect(url_for("auth.login"))

    db = firestore.client()

    # KPI Stats
    admin_stats = AdminService.get_admin_stats(db)

    # Email Verification Setting
    setting_ref = db.collection("settings").document("enforceEmailVerification")
    email_verification_setting = setting_ref.get()

    # RESOLVED CONFLICT: Fetch all users including private ones for management
    users = UserService.get_all_users(db, limit=50, public_only=False)

    return render_template(
        "admin/admin.html",
        admin_stats=admin_stats,
        users=users,
        email_verification_setting=email_verification_setting.to_dict()
        if email_verification_setting.exists
        else {"value": False},
    )

# ... (merge_ghost, announcement, and toggle_email_verification remain unchanged)

@bp.route("/merge_players", methods=["GET", "POST"])
@login_required(admin_required=True)
def merge_players() -> Union[str, Response]:
    """Merge two player accounts (Source -> Target). Source is deleted."""
    # RESOLVED CONFLICT: Admin needs to see non-public (ghost) users to merge them
    users = UserService.get_all_users(
        firestore.client(), exclude_ids=[], public_only=False
    )

    # Sort users for the dropdown (Real users first, then Ghosts)
    sorted_users = sorted(
        users, key=lambda u: (u.get("is_ghost", False), u.get("name", "").lower())
    )

    if request.method == "POST":
        source_id = request.form.get("source_id")
        target_id = request.form.get("target_id")

        if not source_id or not target_id:
            flash("Source and Target IDs are required.", "error")
            return redirect(url_for("admin.merge_players"))

        if source_id == target_id:
            flash("Source and Target cannot be the same user.", "error")
            return redirect(url_for("admin.merge_players"))

        try:
            UserService.merge_users(firestore.client(), source_id, target_id)
            flash("Players merged successfully. Source account deleted.", "success")
        except Exception as e:
            flash(f"Error merging players: {str(e)}", "error")

        return redirect(url_for("admin.merge_players"))

    return render_template("admin/merge_players.html", users=sorted_users)

# ... (remaining routes remain unchanged)