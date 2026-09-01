"""Membership routes for the group blueprint."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from google.cloud.firestore import Client

from firebase_admin import firestore
from flask import (
    Response,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

from pickaladder.auth.decorators import login_required
from pickaladder.constants.messages import COMMON_MESSAGES, GROUP_MESSAGES
from pickaladder.group import bp
from pickaladder.group.forms import InviteByEmailForm, InviteFriendForm
from pickaladder.group.routes.discovery import _handle_referrer
from pickaladder.group.services.group_service import (
    AccessDenied,
    GroupNotFound,
    GroupService,
)
from pickaladder.group.utils import (
    friend_group_members,
    get_random_joke,
    send_invite_email_background,
)
from pickaladder.user import UserService


def _handle_invite_friend_form(
    db: Client, group_id: str, context: dict[str, Any]
) -> tuple[InviteFriendForm, Any | None]:
    form = InviteFriendForm()
    form.friend.choices = [
        (f.id, f.to_dict().get("name", f.id)) for f in context["eligible_friends"]
    ]
    if not (form.validate_on_submit() and "friend" in request.form):
        return form, None
    try:
        GroupService.invite_friend(db, group_id, form.friend.data)
        flash(GROUP_MESSAGES["FRIEND_INVITE_SUCCESS"], "success")
        return form, redirect(url_for(".view_group", group_id=group_id))
    except Exception as e:
        flash(COMMON_MESSAGES["UNEXPECTED_ERROR"].format(error=e), "danger")
    return form, None


def _handle_invite_email_form(
    db: Client, group_id: str, group_name: str
) -> tuple[InviteByEmailForm, Any | None]:
    form = InviteByEmailForm()
    if not (form.validate_on_submit() and "email" in request.form):
        return form, None

    try:
        if email := form.email.data:
            GroupService.invite_by_email(
                db, group_id, group_name, email, form.name.data or "Friend", g.user.uid
            )
            flash(
                GROUP_MESSAGES["INVITATION_SENDING"].format(email=email.lower()),
                "success",
            )
            return form, redirect(url_for(".view_group", group_id=group_id))
    except Exception as e:
        flash(GROUP_MESSAGES["INVITE_CREATE_ERROR"].format(error=e), "danger")
    return form, None


def _check_group_admin(db: Client, group_id: str, user_id: str) -> bool:
    group_ref = db.collection("groups").document(group_id)
    group = group_ref.get()
    if not group.exists:
        return False
    return GroupService.is_group_admin(group.to_dict() or {}, user_id)


def _get_invite_data(db: Client, token: str) -> tuple[Any, dict[str, Any] | None, Any]:
    invite_ref = db.collection("group_invites").document(token)
    return (
        invite_ref,
        invite_ref.get().to_dict() if invite_ref.get().exists else None,
        invite_ref.get(),
    )


def _get_group_context(db: Client, group_id: str) -> dict[str, Any]:
    player_a_id = request.args.get("playerA")
    player_b_id = request.args.get("playerB")
    return GroupService.get_group_details(
        db, group_id, g.user.uid, player_a_id, player_b_id
    )


@bp.route("/<string:group_id>", methods=["GET", "POST"])
@login_required
def view_group(group_id: str) -> Response | str | dict[str, Any]:
    _handle_referrer()
    db = firestore.client()
    try:
        context = GroupService.get_group_details(
            db,
            group_id,
            g.user.uid,
            request.args.get("playerA"),
            request.args.get("playerB"),
        )
    except GroupNotFound:
        flash(GROUP_MESSAGES["NOT_FOUND"], "danger")
        return redirect(url_for(".view_groups"))  # type: ignore
    except AccessDenied:
        flash(GROUP_MESSAGES["ACCESS_DENIED"], "danger")
        return redirect(url_for(".view_groups"))  # type: ignore

    form, resp = _handle_invite_friend_form(db, group_id, context)
    if resp:
        return resp

    invite_email_form, resp = _handle_invite_email_form(
        db, group_id, context["group"].get("name", "Unknown Group")
    )
    if resp:
        return resp

    from pickaladder.season.services import SeasonService

    context["seasons"] = SeasonService.get_seasons_for_group(db, group_id)
    return render_template(
        "group.html", form=form, invite_email_form=invite_email_form, **context
    )


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


@bp.route("/invite/<token>/resend", methods=["POST"])
@login_required
def resend_invite(token: str) -> Response | str | dict[str, Any]:
    """Resend a group invitation."""
    db = firestore.client()
    invite_ref, data, invite = _get_invite_data(db, token)
    if not data:
        flash(GROUP_MESSAGES["INVITE_NOT_FOUND"], "danger")
        return redirect(url_for("auth.login"))  # type: ignore

    group_id = data.get("group_id", "")

    # Check permissions
    if not _check_group_admin(db, group_id, g.user.uid):
        flash(GROUP_MESSAGES["PERMISSION_DENIED"], "danger")
        return redirect(url_for(".view_group", group_id=group_id))  # type: ignore

    new_email = request.form.get("email")
    if new_email:
        data["email"] = new_email
        invite_ref.update({"email": new_email})

    invite_ref.update({"status": "sending"})

    invite_url = url_for(".handle_invite", token=token, _external=True)
    group_ref = db.collection("groups").document(group_id)
    group = group_ref.get()
    if not group.exists:
        flash(GROUP_MESSAGES["NOT_FOUND"], "danger")
        return redirect(url_for("auth.login"))  # type: ignore
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
    invite_ref, data, invite = _get_invite_data(db, token)
    if not data:
        flash(GROUP_MESSAGES["INVITE_NOT_FOUND"], "danger")
        return redirect(url_for("auth.login"))  # type: ignore

    group_id = data.get("group_id", "")
    if not _check_group_admin(db, group_id, g.user.uid):
        flash(GROUP_MESSAGES["PERMISSION_DENIED"], "danger")
        return redirect(url_for(".view_group", group_id=group_id))  # type: ignore

    invite_ref.delete()
    flash(GROUP_MESSAGES["INVITE_REMOVED"], "success")
    return redirect(url_for(".view_group", group_id=group_id))  # type: ignore


@bp.route("/invite/<token>")
@login_required
def handle_invite(token: str) -> Response | str | dict[str, Any]:
    db = firestore.client()
    invite_ref, invite_data, invite = _get_invite_data(db, token)
    if not invite_data:
        flash(GROUP_MESSAGES["INVALID_LINK"], "danger")
        return redirect(url_for("auth.login"))  # type: ignore

    if invite_data.get("used"):
        flash(GROUP_MESSAGES["INVITE_ALREADY_USED"], "warning")
        return redirect(url_for("auth.login"))  # type: ignore

    group_id = invite_data.get("group_id", "")
    group_ref = db.collection("groups").document(group_id)
    user_ref = db.collection("users").document(g.user.uid)

    try:
        if email := invite_data.get("email"):
            UserService.merge_ghost_user(db, user_ref, email)
        group_ref.update({"members": firestore.ArrayUnion([user_ref])})
        invite_ref.update({"used": True, "used_by": g.user.uid})
        friend_group_members(db, group_id, user_ref)
        flash(GROUP_MESSAGES["WELCOME"], "success")
        return redirect(url_for(".view_group", group_id=group_id))  # type: ignore
    except Exception as e:
        flash(GROUP_MESSAGES["JOIN_ERROR"].format(error=e), "danger")
        return redirect(url_for("auth.login"))  # type: ignore


@bp.route("/<string:group_id>/join", methods=["POST"])
@login_required
def join_group(group_id: str) -> Response | str | dict[str, Any]:
    """Join a group."""
    db = firestore.client()
    group_ref = db.collection("groups").document(group_id)
    user_ref = db.collection("users").document(g.user.uid)

    group_doc = group_ref.get()
    if not group_doc.exists:
        flash(GROUP_MESSAGES["NOT_FOUND"], "danger")
        return redirect(url_for(".view_groups"))  # type: ignore
    if (group_doc.to_dict() or {}).get("join_policy", "REQUEST") != "OPEN":
        flash("You are not allowed to join this group directly.", "danger")
        return redirect(url_for(".view_group", group_id=group_id))  # type: ignore

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
