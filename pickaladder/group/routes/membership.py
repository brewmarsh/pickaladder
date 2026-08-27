"""Membership routes for the group blueprint."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from google.cloud.firestore import Client

from firebase_admin import firestore
from flask import (
    Response,
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
)


def _handle_invite_friend_form(
    db: Client,
    group_id: str,
    context: dict[str, Any],
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
    db: Client,
    group_id: str,
    group_name: str,
) -> tuple[InviteByEmailForm, Any | None]:
    """Process InviteByEmailForm submission."""
    invite_email_form = InviteByEmailForm()
    if invite_email_form.validate_on_submit() and "email" in request.form:
        try:
            name = invite_email_form.name.data or "Friend"
            email = invite_email_form.email.data
            if email:
                GroupService.invite_by_email(
                    db,
                    group_id,
                    group_name,
                    email,
                    name,
                    g.user.uid,
                )
                flash(
                    GROUP_MESSAGES["INVITATION_SENDING"].format(email=email.lower()),
                    "success",
                )
                return invite_email_form, redirect(
                    url_for(".view_group", group_id=group_id),
                )
        except Exception as e:
            flash(GROUP_MESSAGES["INVITE_CREATE_ERROR"].format(error=e), "danger")
    return invite_email_form, None


@bp.route("/<string:group_id>", methods=["GET", "POST"])
@login_required
def view_group(group_id: str) -> Response | str | dict[str, Any]:
    """Display a single group's page."""
    _handle_referrer()

    db = firestore.client()
    player_a_id = request.args.get("playerA")
    player_b_id = request.args.get("playerB")

    try:
        context = GroupService.get_group_details(
            db,
            group_id,
            g.user.uid,
            player_a_id,
            player_b_id,
        )
    except GroupNotFound:
        flash(GROUP_MESSAGES["NOT_FOUND"], "danger")
        return redirect(url_for("group.view_groups"))  # type: ignore
    except AccessDenied:
        flash(GROUP_MESSAGES["ACCESS_DENIED"], "danger")
        return redirect(url_for("group.view_groups"))  # type: ignore

    form, resp = _handle_invite_friend_form(db, group_id, context)
    if resp:
        return resp

    invite_email_form, resp = _handle_invite_email_form(
        db,
        group_id,
        context["group"].get("name", "Unknown Group"),
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
        **context,
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

    return redirect(url_for("group.view_group", group_id=group_id))  # type: ignore


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
        return redirect(url_for("group.view_groups"))  # type: ignore

    if (group_doc.to_dict() or {}).get("join_policy") != "OPEN":
        flash("This group is not open to join.", "danger")
        return redirect(url_for("group.view_group", group_id=group_id))  # type: ignore

    try:
        group_ref.update({"members": firestore.ArrayUnion([user_ref])})
        friend_group_members(db, group_id, user_ref)
        flash(GROUP_MESSAGES["JOIN_SUCCESS"], "success")
    except Exception as e:
        flash(GROUP_MESSAGES["JOIN_TRY_ERROR"].format(error=e), "danger")

    return redirect(url_for("group.view_group", group_id=group_id))  # type: ignore


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

    return redirect(url_for("group.view_group", group_id=group_id))  # type: ignore
