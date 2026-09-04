"""User management routes."""

from typing import Any

from firebase_admin import firestore
from flask import flash, g, redirect, request, url_for

from pickaladder.admin import bp
from pickaladder.admin.routes import _lookup_user_by_identifier, _perform_user_deletion
from pickaladder.admin.services import AdminService
from pickaladder.auth.decorators import login_required
from pickaladder.constants.messages import ADMIN_MESSAGES, COMMON_MESSAGES


@bp.route("/delete_user", methods=["POST"])
@login_required(admin_required=True)
def admin_delete_user() -> Any:
    """Delete a user by ID or Email."""
    user_identifier = request.form.get("user_identifier")
    if not user_identifier:
        flash(ADMIN_MESSAGES["USER_ID_EMAIL_REQUIRED"], "danger")
        return redirect(url_for(".view_users"))

    db = firestore.client()
    uid, email = _lookup_user_by_identifier(db, user_identifier)
    if uid:
        _perform_user_deletion(db, uid, email)
    else:
        flash(
            ADMIN_MESSAGES["USER_NOT_FOUND"].format(identifier=user_identifier),
            "danger",
        )
    return redirect(url_for(".view_users"))


@bp.route("/delete_user/<string:user_id>", methods=["POST"])
@login_required(admin_required=True)
def delete_user(user_id: str) -> Any:
    """Delete a user from Firebase Auth and Firestore."""
    try:
        db = firestore.client()
        AdminService.delete_user(db, user_id)
        AdminService.log_action(db, g.user.uid, user_id, "delete_user")
        flash(ADMIN_MESSAGES["USER_DELETE_SUCCESS"], "success")
    except Exception as e:
        flash(COMMON_MESSAGES["GENERIC_ERROR"].format(error=e), "danger")
    return redirect(url_for(".view_users"))


@bp.route("/promote_user/<string:user_id>", methods=["POST"])
@login_required(admin_required=True)
def promote_user(user_id: str) -> Any:
    """Promote a user to admin status in Firestore."""
    try:
        db = firestore.client()
        name = AdminService.promote_user(db, user_id)
        AdminService.log_action(db, g.user.uid, user_id, "promote_user")
        flash(ADMIN_MESSAGES["ADMIN_PROMOTION"].format(name=name), "success")
    except Exception as e:
        flash(COMMON_MESSAGES["GENERIC_ERROR"].format(error=e), "danger")
    return redirect(url_for(".view_users"))


@bp.route("/verify_user/<string:user_id>", methods=["POST"])
@login_required(admin_required=True)
def verify_user(user_id: str) -> Any:
    """Manually verify a user's email."""
    try:
        AdminService.verify_user(firestore.client(), user_id)
        flash(ADMIN_MESSAGES["EMAIL_VERIFIED_SUCCESS"], "success")
    except Exception as e:
        flash(COMMON_MESSAGES["GENERIC_ERROR"].format(error=e), "danger")
    return redirect(url_for(".view_users"))
