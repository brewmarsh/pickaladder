"""Membership routes for the group blueprint."""

from __future__ import annotations

from typing import Any

from firebase_admin import firestore
from flask import current_app, flash, g, redirect, render_template, request, url_for

from pickaladder.auth.decorators import login_required
from pickaladder.constants.messages import COMMON_MESSAGES, GROUP_MESSAGES
from pickaladder.user import UserService
from pickaladder.group import bp
from pickaladder.group.forms import InviteByEmailForm, InviteFriendForm
from pickaladder.group.services.group_service import AccessDenied, GroupNotFound, GroupService
from pickaladder.group.utils import friend_group_members, get_random_joke, send_invite_email_background
from pickaladder.group.routes.discovery import _handle_referrer


def _handle_invite_friend_form(
    db: 'Client', group_id: str, context: dict[str, object]
) -> tuple[InviteFriendForm, Any | None]:
    """Process InviteFriendForm submission."""
    form = InviteFriendForm()
    form.friend.choices = [
        (friend.id, friend.to_dict().get("name", friend.id))
        for friend in context["eligible_friends"]
    ]

    if form.validate_on_submit() and "friend" in request.form:
        try:
            GroupService.invite_friend(db, group_id, form.friend.data)
            flash(GROUP_MESSAGES["FRIEND_INVITE_SUCCESS"], "success")
            return form, redirect(url_for(".view_group", group_id=group_id))
        except Exception as e:
            flash(COMMON_MESSAGES["UNEXPECTED_ERROR"].format(error=e), "danger")
    return form, None


def _handle_invite_email_form(
    db: 'Client', group_id: str, group_name: str
) -> tuple[InviteByEmailForm, Any | None]:
    """Process InviteByEmailForm submission."""
    invite_email_form = InviteByEmailForm()
    if invite_email_form.validate_on_submit() and "email" in request.form:
        try:
            name = invite_email_form.name.data or "Friend"
            email = invite_email_form.email.data
            if email:
                GroupService.invite_by_email(
                    db, group_id, group_name, email, name, g.user.uid
                )
                flash(
                    GROUP_MESSAGES["INVITATION_SENDING"].format(email=email.lower()),
                    "success",
                )
                return invite_email_form, redirect(
                    url_for(".view_group", group_id=group_id)
                )
        except Exception as e:
            flash(GROUP_MESSAGES["INVITE_CREATE_ERROR"].format(error=e), "danger")
    return invite_email_form, None


@bp.route("/<string:group_id>", methods=["GET", "POST"])
@login_required
def view_group(group_id: str) -> 'Response' | str | dict[str, object]:
    """Display a single group's page."""
    _handle_referrer()

    db = firestore.client()
    player_a_id = request.args.get("playerA")
    player_b_id = request.args.get("playerB")

    try:
        context = GroupService.get_group_details(
            db, group_id, g.user.uid, player_a_id, player_b_id
        )
    except GroupNotFound:
        flash(GROUP_MESSAGES["NOT_FOUND"], "danger")
        return redirect(url_for(".view_groups"))
    except AccessDenied:
        flash(GROUP_MESSAGES["ACCESS_DENIED"], "danger")
        return redirect(url_for(".view_groups"))

    form, resp = _handle_invite_friend_form(db, group_id, context)
    if resp:
        return resp

    invite_email_form, resp = _handle_invite_email_form(
        db, group_id, context["group"].get("name", "Unknown Group")
    )
    if resp:
        return resp

    # 10. Fetch Seasons
    from pickaladder.season.services import SeasonService
    context["seasons"] = SeasonService.get_seasons_for_group(db, group_id)

    return render_template(
        "group.html",
        form=form,
        invite_email_form=invite_email_form,
        **context
    )


@bp.route("/<string:group_id>/request_join", methods=["POST"])
@login_required
def request_membership(group_id: str) -> 'Response' | str | dict[str, object]:
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

    return redirect(url_for(".view_group", group_id=group_id))


@bp.route("/invite/<token>/resend", methods=["POST"])
@login_required
def resend_invite(token: str) -> 'Response' | str | dict[str, object]:
    """Resend a group invitation."""
    db = firestore.client()
    invite_ref = db.collection("group_invites").document(token)
    invite = invite_ref.get()

    if not invite.exists:
        flash(GROUP_MESSAGES["INVITE_NOT_FOUND"], "danger")
        return redirect(url_for("auth.login"))

    data = invite.to_dict() or {}
    group_id = data.get("group_id", "")

    # Check permissions
    group_ref = db.collection("groups").document(group_id)
    group = group_ref.get()
    if not group.exists:
        flash(GROUP_MESSAGES["NOT_FOUND"], "danger")
        return redirect(url_for("auth.login"))

    if not GroupService.is_group_admin(group.to_dict() or {}, g.user.uid):
        flash(GROUP_MESSAGES["PERMISSION_DENIED"], "danger")
        return redirect(url_for(".view_group", group_id=group_id))

    new_email = request.form.get("email")
    if new_email:
        data["email"] = new_email
        invite_ref.update({"email": new_email})

    invite_ref.update({"status": "sending"})

    invite_url = url_for(".handle_invite", token=token, _external=True)
    email_data = {
        "to": data.get("email"),
        "subject": f"Join {group.to_dict().get('name')} on pickaladder!", # type: ignore
        "template": "email/group_invite.html",
        "name": data.get("name"),
        "group_name": group.to_dict().get("name"), # type: ignore
        "invite_url": invite_url,
        "joke": get_random_joke(),
    }

    send_invite_email_background(
        current_app._get_current_object(),  # type: ignore[attr-defined]
        token,
        email_data,
    )
    flash(GROUP_MESSAGES["INVITE_RESENDING"].format(email=data.get("email")), "toast")
    return redirect(url_for(".view_group", group_id=group_id))


@bp.route("/invite/<token>/delete", methods=["POST"])
@login_required
def delete_invite(token: str) -> 'Response' | str | dict[str, object]:
    """Delete a pending invitation."""
    db = firestore.client()
    invite_ref = db.collection("group_invites").document(token)
    invite = invite_ref.get()

    if not invite.exists:
        flash(GROUP_MESSAGES["INVITE_NOT_FOUND"], "danger")
        return redirect(url_for("auth.login"))

    group_id = invite.to_dict().get("group_id") # type: ignore
    group_ref = db.collection("groups").document(group_id)
    group = group_ref.get()

    if not group.exists:
        flash(GROUP_MESSAGES["NOT_FOUND"], "danger")
        return redirect(url_for("auth.login"))

    if not GroupService.is_group_admin(group.to_dict() or {}, g.user.uid):
        flash(GROUP_MESSAGES["PERMISSION_DENIED"], "danger")
        return redirect(url_for(".view_group", group_id=group_id))

    invite_ref.delete()
    flash(GROUP_MESSAGES["INVITE_REMOVED"], "success")
    return redirect(url_for(".view_group", group_id=group_id))


@bp.route("/invite/<token>")
@login_required
def handle_invite(token: str) -> 'Response' | str | dict[str, object]:
    """Handle an invitation link."""
    db = firestore.client()
    invite_ref = db.collection("group_invites").document(token)
    invite = invite_ref.get()

    if not invite.exists:
        flash(GROUP_MESSAGES["INVALID_LINK"], "danger")
        return redirect(url_for("auth.login"))

    invite_data = invite.to_dict() or {}
    if invite_data.get("used"):
        flash(GROUP_MESSAGES["INVITE_ALREADY_USED"], "warning")
        return redirect(url_for("auth.login"))

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
        return redirect(url_for(".view_group", group_id=group_id))
    except Exception as e:
        flash(GROUP_MESSAGES["JOIN_ERROR"].format(error=e), "danger")
        return redirect(url_for("auth.login"))


@bp.route("/<string:group_id>/join", methods=["POST"])
@login_required
def join_group(group_id: str) -> 'Response' | str | dict[str, object]:
    """Join a group."""
    db = firestore.client()
    group_ref = db.collection("groups").document(group_id)
    user_ref = db.collection("users").document(g.user.uid)

    try:
        group_ref.update({"members": firestore.ArrayUnion([user_ref])})
        friend_group_members(db, group_id, user_ref)
        flash(GROUP_MESSAGES["JOIN_SUCCESS"], "success")
    except Exception as e:
        flash(GROUP_MESSAGES["JOIN_TRY_ERROR"].format(error=e), "danger")

    return redirect(url_for(".view_group", group_id=group_id))


@bp.route("/<string:group_id>/leave", methods=["POST"])
@login_required
def leave_group(group_id: str) -> 'Response' | str | dict[str, object]:
    """Leave a group."""
    db = firestore.client()
    group_ref = db.collection("groups").document(group_id)
    user_ref = db.collection("users").document(g.user.uid)

    try:
        group_ref.update({"members": firestore.ArrayRemove([user_ref])})
        flash(GROUP_MESSAGES["LEAVE_SUCCESS"], "success")
    except Exception as e:
        flash(GROUP_MESSAGES["LEAVE_ERROR"].format(error=e), "danger")

    return redirect(url_for(".view_group", group_id=group_id))
