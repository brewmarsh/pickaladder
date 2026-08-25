from typing import Any

from firebase_admin import firestore
from flask import flash, g, redirect, request, url_for
from werkzeug.wrappers import Response

from pickaladder.auth.decorators import login_required
from pickaladder.constants.messages import COMMON_MESSAGES, GROUP_MESSAGES
from pickaladder.group import bp
from pickaladder.group.services.group_service import GroupService
from pickaladder.group.utils import friend_group_members


@bp.route("/<string:group_id>/request_join", methods=["POST"])
@login_required
def request_membership(group_id: str) -> Response | str | dict[str, Any]:
    """Request to join a group."""
    db = firestore.client()
    message = request.form.get("message")
    try:
        GroupService.create_membership_request(db, group_id, g.user.uid, message)
        flash("Your request to join has been sent to the group admins.", "success")
    except ValueError as e:
        flash(str(e), "warning")
    except Exception as e:
        flash(COMMON_MESSAGES["GENERIC_ERROR"].format(error=e), "danger")

    return redirect(url_for(".view_group", group_id=group_id))  # type: ignore


@bp.route("/<string:group_id>/join", methods=["POST"])
@login_required
def join_group(group_id: str) -> Response | str | dict[str, Any]:
    """Join a group."""
    db = firestore.client()
    group_ref = db.collection("groups").document(group_id)

    # 🛡️ Sentinel: Security fix - Validate join_policy to prevent authorization bypass (IDOR)
    group_snap = group_ref.get()
    if not group_snap.exists:
        flash(GROUP_MESSAGES["NOT_FOUND"], "danger")
        return redirect(url_for(".view_groups"))  # type: ignore

    group_data = group_snap.to_dict() or {}
    if group_data.get("join_policy") != "OPEN":
        flash(GROUP_MESSAGES["PERMISSION_DENIED"], "danger")
        return redirect(url_for(".view_group", group_id=group_id))  # type: ignore

    user_ref = db.collection("users").document(g.user.uid)

    try:
        group_ref.update({"members": firestore.ArrayUnion([user_ref])})
        friend_group_members(db, group_id, user_ref)
        flash(GROUP_MESSAGES["JOIN_SUCCESS"], "success")
    except Exception as e:
        flash(GROUP_MESSAGES["JOIN_TRY_ERROR"].format(error=e), "danger")

    return redirect(url_for(".view_group", group_id=group_id))  # type: ignore


@bp.route("/<string:group_id>/leave", methods=["POST"])
@login_required
def leave_group(group_id: str) -> Response | str | dict[str, Any]:
    """Leave a group."""
    db = firestore.client()
    group_ref = db.collection("groups").document(group_id)
    user_ref = db.collection("users").document(g.user.uid)

    try:
        group_ref.update({"members": firestore.ArrayRemove([user_ref])})
        flash(GROUP_MESSAGES["LEAVE_SUCCESS"], "success")
    except Exception as e:
        flash(GROUP_MESSAGES["LEAVE_ERROR"].format(error=e), "danger")

    return redirect(url_for(".view_group", group_id=group_id))  # type: ignore
