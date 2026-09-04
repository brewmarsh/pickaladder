"""Admin routes for the application."""

from __future__ import annotations

from typing import TYPE_CHECKING

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

from pickaladder.auth.decorators import login_required
from pickaladder.constants.messages import (
    ADMIN_MESSAGES,
    AUTH_MESSAGES,
    COMMON_MESSAGES,
)
from pickaladder.extensions import cache
from pickaladder.user import UserService

from . import bp
from .services import AdminService

if TYPE_CHECKING:
    from werkzeug.wrappers import Response

MIN_USERS_FOR_MATCH_GENERATION = 2


@bp.route("/")
@login_required(admin_required=True)
def admin() -> str | Response:
    """Render the main admin users list (legacy /)."""
    return redirect(url_for(".dashboard"))


@bp.route("/dashboard")
@login_required(admin_required=True)
def dashboard() -> str | Response:
    """Render the operational admin dashboard."""
    if not g.user or (not g.user.is_admin and not g.get("is_impersonating")):
        flash(AUTH_MESSAGES["UNAUTHORIZED"], "danger")
        return redirect(url_for("auth.login"))

    db = firestore.client()
    from pickaladder.services.error_service import ErrorService

    growth_data = AdminService.get_growth_metrics(db)
    recent_errors = ErrorService.get_recent_errors(db, limit=5)
    audit_logs = AdminService.get_recent_audit_logs(db, limit=5)

    # Optional: Resolve admin names for audit logs
    admin_ids = list({log["admin_id"] for log in audit_logs if log.get("admin_id")})
    admin_names = {}
    if admin_ids:
        # Simple fetch, in production use batch get
        for aid in admin_ids:
            u = UserService.get_user_by_id(db, aid)
            admin_names[aid] = UserService.smart_display_name(u) if u else aid

    for log in audit_logs:
        log["admin_name"] = admin_names.get(log.get("admin_id"))

    return render_template(
        "admin/dashboard.html",
        growth_data=growth_data,
        recent_errors=recent_errors,
        audit_logs=audit_logs,
    )


@bp.route("/users")
@login_required(admin_required=True)
def view_users() -> str | Response:
    """Render the user management page."""
    if not g.user or (not g.user.is_admin and not g.get("is_impersonating")):
        flash(AUTH_MESSAGES["UNAUTHORIZED"], "danger")
        return redirect(url_for("auth.login"))

    db = firestore.client()
    admin_stats = AdminService.get_admin_stats(db)
    setting_ref = db.collection("settings").document("enforceEmailVerification")
    email_verification_setting = setting_ref.get()
    users, _ = UserService.get_all_users(db, limit=100, public_only=False)

    return render_template(
        "admin/admin.html",
        admin_stats=admin_stats,
        users=users,
        email_verification_setting=email_verification_setting.to_dict()
        if email_verification_setting.exists
        else {"value": "false"},
    )


@bp.route("/merge-ghost", methods=["POST"])
@login_required(admin_required=True)
def merge_ghost() -> Response:
    """Merge a ghost account into a real user profile."""
    target_user_id = request.form.get("target_user_id")
    ghost_email = request.form.get("ghost_email")

    if not target_user_id or not ghost_email:
        flash(ADMIN_MESSAGES["MERGE_REQUIRED_FIELDS"], "danger")
        return redirect(url_for(".view_users"))

    db = firestore.client()
    real_user_ref = db.collection("users").document(target_user_id)
    try:
        if UserService.merge_ghost_user(db, real_user_ref, ghost_email):
            flash(ADMIN_MESSAGES["GHOST_MERGE_SUCCESS"], "success")
        else:
            flash(ADMIN_MESSAGES["GHOST_MERGE_FAILED"], "danger")
    except Exception as e:
        flash(COMMON_MESSAGES["GENERIC_ERROR"].format(error=e), "danger")

    return redirect(url_for(".view_users"))


@bp.route("/announcement", methods=["POST"])
@login_required(admin_required=True)
def announcement() -> Response:
    """Update the global system announcement."""
    db = firestore.client()
    try:
        announcement_text = request.form.get("announcement_text")
        is_active = request.form.get("is_active") == "on"
        level = request.form.get("level", "info")
        db.collection("system").document("settings").set(
            {
                "announcement_text": announcement_text,
                "is_active": is_active,
                "level": level,
            },
            merge=True,
        )
        AdminService.log_action(
            db,
            g.user.uid,
            None,
            "update_announcement",
            {"text": announcement_text, "active": is_active, "level": level},
        )
        cache.delete("global_announcement")
        flash(ADMIN_MESSAGES["ANNOUNCEMENT_UPDATED"], "success")
    except Exception as e:
        flash(ADMIN_MESSAGES["ANNOUNCEMENT_ERROR"].format(error=e), "danger")
    return redirect(url_for(".view_users"))


@bp.route("/toggle_email_verification", methods=["POST"])
@login_required(admin_required=True)
def toggle_email_verification() -> Response:
    """Toggle the global setting for requiring email verification."""
    db = firestore.client()
    try:
        new_val = AdminService.toggle_setting(db, "enforceEmailVerification")
        status = "enabled" if new_val else "disabled"
        flash(
            ADMIN_MESSAGES["EMAIL_VERIFY_TOGGLED"].format(status=status),
            "success",
        )
    except Exception as e:
        flash(COMMON_MESSAGES["GENERIC_ERROR"].format(error=e), "danger")
    return redirect(url_for(".view_users"))


def _lookup_user_by_identifier(
    db: firestore.Client,
    identifier: str,
) -> tuple[str | None, str | None]:
    """Look up a user UID and email by their identifier (ID or Email)."""
    user_doc = db.collection("users").document(identifier).get()
    if user_doc.exists:
        return user_doc.id, user_doc.to_dict().get("email")

    users = list(
        db.collection("users")
        .where(filter=firestore.FieldFilter("email", "==", identifier))
        .limit(1)
        .stream(),
    )
    if users:
        return users[0].id, users[0].to_dict().get("email")
    return None, None


def _perform_user_deletion(db: firestore.Client, uid: str, email: str | None) -> None:
    """Orchestrate the deletion of a user and flash results."""
    try:
        AdminService.delete_user(db, uid)
        AdminService.log_action(db, g.user.uid, uid, "delete_user", {"email": email})
        flash(
            ADMIN_MESSAGES["USER_DELETED_COUNT"].format(identifier=email or uid),
            "success",
        )
    except Exception as e:
        flash(COMMON_MESSAGES["GENERIC_ERROR"].format(error=e), "danger")


@bp.route("/impersonate/<string:user_id>")
@login_required(admin_required=True)
def impersonate(user_id: str) -> Response:
    """Start impersonating another user."""
    session["impersonate_id"] = user_id
    doc = firestore.client().collection("users").document(user_id).get()
    name = doc.to_dict().get("name", "User") if doc.exists else "User"
    flash(ADMIN_MESSAGES["IMPERSONATION_START"].format(name=name), "success")
    return redirect(url_for("user.dashboard"))


@bp.route("/stop_impersonating")
@login_required
def stop_impersonating() -> Response:
    """Stop impersonating and return to admin profile."""
    session.pop("impersonate_id", None)
    flash(ADMIN_MESSAGES["ADMIN_WELCOME"], "success")
    return redirect(url_for("admin.admin"))
