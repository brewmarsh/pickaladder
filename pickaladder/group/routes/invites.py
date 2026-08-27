"""Routes for handling group invitations."""

from __future__ import annotations

from typing import Any

from firebase_admin import firestore
from flask import Response, current_app, flash, g, redirect, request, url_for

from pickaladder.auth.decorators import login_required
from pickaladder.constants.messages import GROUP_MESSAGES
from pickaladder.group import bp
from pickaladder.group.services.group_service import GroupService
from pickaladder.group.utils import (
    friend_group_members,
    get_random_joke,
    send_invite_email_background,
)
from pickaladder.user import UserService


@bp.route("/invite/<token>/resend", methods=["POST"])
@login_required
def resend_invite(token: str) -> Response | str | dict[str, Any]:
    """Resend a group invitation."""
    db = firestore.client()
    invite_ref = db.collection("group_invites").document(token)
    invite = invite_ref.get()

    if not invite.exists:
        flash(GROUP_MESSAGES["INVITE_NOT_FOUND"], "danger")
        return redirect(url_for("auth.login"))  # type: ignore

    data = invite.to_dict() or {}
    group_id = data.get("group_id", "")

    # Check permissions
    group_ref = db.collection("groups").document(group_id)
    group = group_ref.get()
    if not group.exists:
        flash(GROUP_MESSAGES["NOT_FOUND"], "danger")
        return redirect(url_for("auth.login"))  # type: ignore

    if not GroupService.is_group_admin(group.to_dict() or {}, g.user.uid):
        flash(GROUP_MESSAGES["PERMISSION_DENIED"], "danger")
        return redirect(url_for(".view_group", group_id=group_id))  # type: ignore

    new_email = request.form.get("email")
    if new_email:
        data["email"] = new_email
        invite_ref.update({"email": new_email})

    invite_ref.update({"status": "sending"})

    invite_url = url_for(".handle_invite", token=token, _external=True)
    email_data = {
        "to": data.get("email"),
        "subject": f"Join {group.to_dict().get('name')} on pickaladder!",  # type: ignore
        "template": "email/group_invite.html",
        "name": data.get("name"),
        "group_name": group.to_dict().get("name"),  # type: ignore
        "invite_url": invite_url,
        "joke": get_random_joke(),
    }

    send_invite_email_background(
        current_app._get_current_object(),  # type: ignore[attr-defined]
        token,
        email_data,
    )
    flash(GROUP_MESSAGES["INVITE_RESENDING"].format(email=data.get("email")), "toast")
    return redirect(url_for(".view_group", group_id=group_id))  # type: ignore


@bp.route("/invite/<token>/delete", methods=["POST"])
@login_required
def delete_invite(token: str) -> Response | str | dict[str, Any]:
    """Delete a pending invitation."""
    db = firestore.client()
    invite_ref = db.collection("group_invites").document(token)
    invite = invite_ref.get()

    if not invite.exists:
        flash(GROUP_MESSAGES["INVITE_NOT_FOUND"], "danger")
        return redirect(url_for("auth.login"))  # type: ignore

    group_id = invite.to_dict().get("group_id")  # type: ignore
    group_ref = db.collection("groups").document(group_id)
    group = group_ref.get()

    if not group.exists:
        flash(GROUP_MESSAGES["NOT_FOUND"], "danger")
        return redirect(url_for("auth.login"))  # type: ignore

    if not GroupService.is_group_admin(group.to_dict() or {}, g.user.uid):
        flash(GROUP_MESSAGES["PERMISSION_DENIED"], "danger")
        return redirect(url_for(".view_group", group_id=group_id))  # type: ignore

    invite_ref.delete()
    flash(GROUP_MESSAGES["INVITE_REMOVED"], "success")
    return redirect(url_for(".view_group", group_id=group_id))  # type: ignore


@bp.route("/invite/<token>")
@login_required
def handle_invite(token: str) -> Response | str | dict[str, Any]:
    """Handle an invitation link."""
    db = firestore.client()
    invite_ref = db.collection("group_invites").document(token)
    invite = invite_ref.get()

    if not invite.exists:
        flash(GROUP_MESSAGES["INVALID_LINK"], "danger")
        return redirect(url_for("auth.login"))  # type: ignore

    invite_data = invite.to_dict() or {}
    if invite_data.get("used"):
        flash(GROUP_MESSAGES["INVITE_ALREADY_USED"], "warning")
        return redirect(url_for("auth.login"))  # type: ignore

    group_id = invite_data.get("group_id", "")
    group_ref = db.collection("groups").document(group_id)
    user_ref = db.collection("users").document(g.user.uid)

    try:
        # Merge ghost user if exists
        invite_email = invite_data.get("email")
        if invite_email:
            UserService.merge_ghost_user(db, user_ref, invite_email)

        # Add user to group
        group_ref.update({"members": firestore.ArrayUnion([user_ref])})
        # Mark invite as used
        invite_ref.update({"used": True, "used_by": g.user.uid})

        # Friend other group members
        friend_group_members(db, group_id, user_ref)

        flash(GROUP_MESSAGES["WELCOME"], "success")
        return redirect(url_for(".view_group", group_id=group_id))  # type: ignore
    except Exception as e:
        flash(GROUP_MESSAGES["JOIN_ERROR"].format(error=e), "danger")
        return redirect(url_for("auth.login"))  # type: ignore
