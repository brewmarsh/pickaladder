from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from google.cloud.firestore import Client

from flask import flash, g, redirect, request, url_for

from pickaladder.constants.messages import COMMON_MESSAGES, GROUP_MESSAGES
from pickaladder.group.forms import InviteByEmailForm, InviteFriendForm
from pickaladder.group.services.group_service import GroupService


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
