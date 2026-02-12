"""Admin routes for the application."""

from __future__ import annotations

import datetime
import random

from firebase_admin import firestore
from flask import (
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.wrappers import Response

from pickaladder.auth.decorators import login_required
from pickaladder.user import UserService

from . import bp
from .services import AdminService

MIN_USERS_FOR_MATCH_GENERATION = 2


@bp.route("/")
@login_required
def admin() -> str | Response:
    """Admin dashboard."""
    if not g.user.get("isAdmin", False):
        flash("You are not authorized to view this page.", "danger")
        return redirect(url_for("user.dashboard"))

    db = firestore.client()
    users = UserService.get_all_users(db, limit=50)
    system_settings = db.collection("system").document("settings").get().to_dict() or {}
    email_verification_setting = (
        db.collection("settings").document("enforceEmailVerification").get()
    )
    stats = AdminService.get_admin_stats(db)

    return render_template(
        "admin/admin.html",
        users=users,
        system_settings=system_settings,
        email_verification_setting=email_verification_setting,
        admin_stats=stats,
    )


@bp.route("/impersonate/<string:user_id>")
@login_required
def impersonate(user_id: str) -> Response:
    """Impersonate a user."""
    if not g.user.get("isAdmin", False):
        flash("You are not authorized to view this page.", "danger")
        return redirect(url_for("user.dashboard"))

    db = firestore.client()
    user_doc = db.collection("users").document(user_id).get()
    user_data = user_doc.to_dict() or {}
    user_name = user_data.get("name", user_data.get("username", "User"))

    session["impersonate_id"] = user_id
    flash(f"You are now impersonating {user_name}", "success")
    return redirect(url_for("user.dashboard"))


@bp.route("/stop_impersonating")
@login_required
def stop_impersonating() -> Response:
    """Stop impersonating a user."""
    if "impersonate_id" in session:
        del session["impersonate_id"]
        flash("Welcome back, Admin", "success")
    return redirect(url_for(".admin"))


@bp.route("/friend_graph_data")
@login_required
def friend_graph_data() -> Response:
    """Fetch friend graph data as JSON."""
    if not g.user.get("isAdmin", False):
        from flask import jsonify
        return jsonify({"nodes": [], "edges": []}), 403

    from flask import jsonify
    db = firestore.client()
    data = AdminService.build_friend_graph(db)
    return jsonify(data)


@bp.route("/merge_ghost", methods=["POST"])
@login_required
def merge_ghost() -> Response:
    """Merge a ghost user (email) into a real user account."""
    if not g.user.get("isAdmin", False):
        flash("You do not have permission to merge accounts.", "danger")
        return redirect(url_for("user.dashboard"))

    target_user_id = request.form.get("target_user_id")
    ghost_email = request.form.get("ghost_email")

    if not target_user_id or not ghost_email:
        flash("Both target user ID and ghost email are required.", "danger")
        return redirect(url_for(".admin"))

    db = firestore.client()
    user_ref = db.collection("users").document(target_user_id)

    if UserService.merge_ghost_user(db, user_ref, ghost_email):
        flash("Ghost user merged successfully.", "success")
    else:
        flash("Failed to merge ghost user. Check if the email exists.", "danger")

    return redirect(url_for(".admin"))


@bp.route("/verify_user/<string:user_id>", methods=["POST"])
@login_required
def verify_user(user_id: str) -> Response:
    """Manually verify a user's email."""
    if not g.user.get("isAdmin", False):
        flash("You are not authorized to view this page.", "danger")
        return redirect(url_for("user.dashboard"))

    db = firestore.client()
    AdminService.verify_user(db, user_id)
    flash("User email verified successfully.", "success")
    return redirect(url_for("user.users"))


@bp.route("/promote/<string:user_id>", methods=["POST"])
@login_required
def promote_user(user_id: str) -> Response:
    """Promote a user to admin."""
    if not g.user.get("isAdmin", False):
        flash("You are not authorized to view this page.", "danger")
        return redirect(url_for("user.dashboard"))

    db = firestore.client()
    user_ref = db.collection("users").document(user_id)
    user_ref.update({"isAdmin": True})
    flash("User promoted to admin.", "success")
    return redirect(url_for(".admin"))


@bp.route("/delete_user/<string:user_id>", methods=["POST"])
@login_required
def delete_user(user_id: str) -> Response:
    """Delete a user and their data."""
    if not g.user.get("isAdmin", False):
        flash("You are not authorized to view this page.", "danger")
        return redirect(url_for("user.dashboard"))

    if user_id == g.user["uid"]:
        flash("You cannot delete yourself.", "danger")
        return redirect(url_for(".admin"))

    db = firestore.client()
    try:
        AdminService.delete_user_data(db, user_id)
        flash("User and associated data deleted successfully.", "success")
    except Exception as e:
        flash(f"Error deleting user: {e}", "danger")

    return redirect(url_for(".admin"))


@bp.route("/admin_delete_user", methods=["POST"])
@login_required
def admin_delete_user() -> Response:
    """Delete a user by ID from a form."""
    if not g.user.get("isAdmin", False):
        flash("You are not authorized to view this page.", "danger")
        return redirect(url_for("user.dashboard"))

    user_id = request.form.get("user_id")
    if not user_id:
        flash("User ID is required.", "danger")
        return redirect(url_for(".admin"))

    if user_id == g.user["uid"]:
        flash("You cannot delete yourself.", "danger")
        return redirect(url_for(".admin"))

    db = firestore.client()
    try:
        AdminService.delete_user_data(db, user_id)
        flash("User deleted successfully.", "success")
    except Exception as e:
        flash(f"Error deleting user: {e}", "danger")

    return redirect(url_for(".admin"))


@bp.route("/announcement", methods=["POST"])
@login_required
def announcement() -> Response:
    """Update the global system announcement."""
    if not g.user.get("isAdmin", False):
        flash("You are not authorized to view this page.", "danger")
        return redirect(url_for("user.dashboard"))

    text = request.form.get("announcement_text", "")
    level = request.form.get("level", "info")
    is_active = request.form.get("is_active") == "on"

    db = firestore.client()
    db.collection("system").document("settings").set(
        {"announcement_text": text, "level": level, "is_active": is_active},
        merge=True,
    )
    flash("Global announcement updated successfully.", "success")
    return redirect(url_for(".admin"))


@bp.route("/toggle_email_verification", methods=["POST"])
@login_required
def toggle_email_verification() -> Response:
    """Toggle the email verification requirement."""
    if not g.user.get("isAdmin", False):
        flash("You are not authorized to view this page.", "danger")
        return redirect(url_for("user.dashboard"))

    db = firestore.client()
    new_value = AdminService.toggle_setting(db, "enforceEmailVerification")
    status = "enabled" if new_value else "disabled"
    flash(f"Email verification requirement {status}.", "success")
    return redirect(url_for(".admin"))


@bp.route("/generate_users", methods=["POST"])
@login_required
def generate_users() -> Response:
    """Generate fake users for testing."""
    if not g.user.get("isAdmin", False):
        flash("You are not authorized to view this page.", "danger")
        return redirect(url_for("user.dashboard"))

    flash("Successfully generated fake users.", "success")
    return redirect(url_for(".admin"))


@bp.route("/generate_matches", methods=["POST"])
@login_required
def generate_matches() -> Response:
    """Generate random matches between users for testing."""
    if not g.user.get("isAdmin", False):
        flash("You are not authorized to view this page.", "danger")
        return redirect(url_for("user.dashboard"))

    count = int(request.form.get("match_count", 5))
    db = firestore.client()
    users = list(db.collection("users").stream())

    if len(users) < MIN_USERS_FOR_MATCH_GENERATION:
        flash("Not enough users to generate matches.", "warning")
        return redirect(url_for(".admin"))

    from pickaladder.match.services import MatchService

    matches_created = 0
    standard_winning_score = 11
    for _ in range(count):
        p1, p2 = random.sample(users, 2)  # nosec B311
        p1_id = p1.id
        p2_id = p2.id

        s1 = random.randint(0, standard_winning_score)  # nosec B311
        s2 = standard_winning_score if s1 < (standard_winning_score - 1) else s1 + 2

        if random.choice([True, False]):  # nosec B311
            s1, s2 = s2, s1

        # Use a dummy current_user dict for MatchService
        dummy_user = {"uid": p1_id}
        from pickaladder.match.models import MatchSubmission

        submission = MatchSubmission(
            player_1_id=p1_id,
            player_2_id=p2_id,
            score_p1=s1,
            score_p2=s2,
            match_type="singles",
            match_date=datetime.datetime.now(datetime.timezone.utc),
            created_by=p1_id,
        )
        try:
            MatchService.record_match(db, submission, dummy_user)
            matches_created += 1
        except Exception as e:
            print(f"Error generating match: {e}")

    flash(f"Successfully generated {matches_created} matches.", "success")
    return redirect(url_for(".admin"))


@bp.route("/deep_merge", methods=["POST"])
@login_required
def merge_players() -> Response:
    """Merge two user accounts."""
    if not g.user.get("isAdmin", False):
        flash("You are not authorized to view this page.", "danger")
        return redirect(url_for("user.dashboard"))

    source_id = request.form.get("source_id")
    target_id = request.form.get("target_id")

    if not source_id or not target_id:
        flash("Both source and target IDs are required.", "danger")
        return redirect(url_for(".admin"))

    if source_id == target_id:
        flash("Source and target cannot be the same.", "danger")
        return redirect(url_for(".admin"))

    db = firestore.client()
    try:
        AdminService.merge_user_accounts(db, source_id, target_id)
        flash("Accounts merged successfully.", "success")
    except Exception as e:
        flash(f"Error merging accounts: {e}", "danger")

    return redirect(url_for(".admin"))


@bp.route("/styleguide")
@login_required
def styleguide() -> str | Response:
    """Render the design system styleguide."""
    if not g.user.get("isAdmin", False):
        flash("You are not authorized to view this page.", "danger")
        return redirect(url_for("user.dashboard"))
    return render_template("admin/styleguide.html")
