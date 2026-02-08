"""Admin routes for the application."""

from typing import Union

from firebase_admin import firestore
from flask import (
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.wrappers import Response

from pickaladder.auth.decorators import login_required
from pickaladder.user.services import UserService

from . import bp
from .services import AdminService


@bp.route("/")
@login_required(admin_required=True)
def admin() -> Union[str, Response]:
    """Render the main admin dashboard."""
    # Authorization check is now here, after g.user is guaranteed to be loaded.
    if not g.user or not g.user.get("isAdmin"):
        flash("You are not authorized to view this page.", "danger")
        return redirect(url_for("auth.login"))

    db = firestore.client()
    setting_ref = db.collection("settings").document("enforceEmailVerification")
    email_verification_setting = setting_ref.get()
    return render_template(
        "admin/dashboard.html",
        email_verification_setting=email_verification_setting.to_dict()
        if email_verification_setting.exists
        else {"value": False},
    )


@bp.route("/merge-ghost", methods=["GET", "POST"])
@login_required(admin_required=True)
def merge_ghost() -> Union[str, Response]:
    """Merge a ghost account into a real user profile."""
    if not g.user or not g.user.get("isAdmin"):
        flash("You are not authorized to view this page.", "danger")
        return redirect(url_for("auth.login"))

    db = firestore.client()

    if request.method == "POST":
        ghost_user_id = request.form.get("ghost_user_id")
        target_user_id = request.form.get("target_user_id")

        if not ghost_user_id or not target_user_id:
            flash("Both Ghost User and Target User are required.", "danger")
            return redirect(url_for(".merge_ghost"))

        if ghost_user_id == target_user_id:
            flash("Source and Target cannot be the same user.", "danger")
            return redirect(url_for(".merge_ghost"))

        try:
            UserService.merge_users(db, ghost_user_id, target_user_id)
            flash("Ghost user merged successfully", "success")
        except Exception as e:
            flash(f"An error occurred: {e}", "danger")

        return redirect(url_for(".admin"))

    # GET: Fetch all users and filter them
    users = UserService.get_all_users(db)
    ghosts = [u for u in users if u.get("is_ghost") is True]
    real_users = [u for u in users if not u.get("is_ghost")]

    return render_template(
        "admin/merge_ghost.html",
        ghosts=sorted(
            ghosts, key=lambda u: u.get("username", u.get("name", "")).lower()
        ),
        real_users=sorted(
            real_users, key=lambda u: u.get("username", u.get("name", "")).lower()
        ),
    )


@bp.route("/toggle_email_verification", methods=["POST"])
@login_required(admin_required=True)
def toggle_email_verification() -> Response:
    """Toggle the global setting for requiring email verification."""
    db = firestore.client()
    try:
        new_value = AdminService.toggle_setting(db, "enforceEmailVerification")
        new_status = "enabled" if new_value else "disabled"
        flash(f"Email verification requirement has been {new_status}.", "success")
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")
    return redirect(url_for(".admin"))


@bp.route("/matches")
@login_required(admin_required=True)
def admin_matches() -> str:
    """Display a list of all matches."""
    db = firestore.client()
    matches_query = (
        db.collection("matches")
        .order_by("createdAt", direction=firestore.Query.DESCENDING)
        .limit(50)
    )
    matches = matches_query.stream()
    # This is a simplified view. A full view would need to resolve player refs.
    return render_template("admin/matches.html", matches=matches)


@bp.route("/delete_match/<string:match_id>", methods=["POST"])
@login_required(admin_required=True)
def admin_delete_match(match_id: str) -> Response:
    """Delete a match document from Firestore."""
    db = firestore.client()
    try:
        db.collection("matches").document(match_id).delete()
        flash("Match deleted successfully.", "success")
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")
    return redirect(url_for(".admin_matches"))


@bp.route("/friend_graph_data")
@login_required(admin_required=True)
def friend_graph_data() -> Union[Response, str, tuple[Response, int]]:
    """Provide data for a network graph of users and their friendships."""
    db = firestore.client()
    try:
        graph_data = AdminService.build_friend_graph(db)
        return jsonify(graph_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/delete_user/<string:user_id>", methods=["POST"])
@login_required(admin_required=True)
def delete_user(user_id: str) -> Response:
    """Delete a user from Firebase Auth and Firestore."""
    db = firestore.client()
    try:
        AdminService.delete_user(db, user_id)
        flash("User deleted successfully.", "success")
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")
    return redirect(url_for("user.users"))


@bp.route("/promote_user/<string:user_id>", methods=["POST"])
@login_required(admin_required=True)
def promote_user(user_id: str) -> Response:
    """Promote a user to admin status."""
    db = firestore.client()
    try:
        username = AdminService.promote_user(db, user_id)
        flash(f"{username} has been promoted to admin.", "success")
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")
    return redirect(url_for("user.users"))


@bp.route("/verify_user/<string:user_id>", methods=["POST"])
@login_required(admin_required=True)
def verify_user(user_id: str) -> Response:
    """Manually verify a user's email."""
    db = firestore.client()
    try:
        AdminService.verify_user(db, user_id)
        flash("User email verified successfully.", "success")
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")
    return redirect(url_for("user.users"))


@bp.route("/merge_players", methods=["GET", "POST"])
@login_required(admin_required=True)
def merge_players() -> Union[str, Response]:
    """Merge two player accounts (Source -> Target). Source is deleted."""
    users = UserService.get_all_users(firestore.client(), exclude_ids=[])

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
            # Call the service to perform the deep merge
            UserService.merge_users(firestore.client(), source_id, target_id)
            flash("Players merged successfully. Source account deleted.", "success")
        except Exception as e:
            flash(f"Error merging players: {str(e)}", "error")

        return redirect(url_for("admin.merge_players"))

    return render_template("admin/merge_players.html", users=sorted_users)