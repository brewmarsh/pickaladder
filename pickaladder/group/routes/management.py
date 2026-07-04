"""Management routes for the group blueprint."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from google.cloud.firestore import Client

from firebase_admin import firestore
from flask import Response, flash, g, redirect, render_template, url_for

from pickaladder.auth.decorators import login_required
from pickaladder.constants.messages import COMMON_MESSAGES, GROUP_MESSAGES
from pickaladder.group import bp
from pickaladder.group.forms import GroupForm
from pickaladder.group.routes.membership import (
    _handle_invite_email_form,
    _handle_invite_friend_form,
)
from pickaladder.group.services.group_service import (
    AccessDenied,
    GroupNotFound,
    GroupService,
)


@bp.route("/<string:group_id>/manage", methods=["GET", "POST"])
@login_required
def manage_group(group_id: str) -> Response | str | dict[str, Any]:
    """Display the group management hub."""
    db = firestore.client()
    try:
        context = GroupService.get_group_details(db, group_id, g.user.uid)
        if not context["is_admin"]:
            flash(GROUP_MESSAGES["ACCESS_DENIED"], "danger")
            return redirect(url_for(".view_group", group_id=group_id))  # type: ignore
    except GroupNotFound:
        flash(GROUP_MESSAGES["NOT_FOUND"], "danger")
        return redirect(url_for(".view_groups"))  # type: ignore
    except AccessDenied:
        flash(GROUP_MESSAGES["ACCESS_DENIED"], "danger")
        return redirect(url_for(".view_groups"))  # type: ignore

    # 1. Invite Email form
    invite_email_form, resp = _handle_invite_email_form(
        db,
        group_id,
        context["group"].get("name", "Unknown Group"),
    )
    if resp:
        return resp

    # 2. Invite Friend form
    invite_friend_form, resp = _handle_invite_friend_form(db, group_id, context)
    if resp:
        return resp

    # 3. Settings form (Update Group)
    form, resp = _handle_edit_group_form(db, group_id, context["group"])
    if resp:
        return resp

    # 4. Fetch Seasons
    from pickaladder.season.services import SeasonService

    context["seasons"] = SeasonService.get_seasons_for_group(db, group_id)

    # 5. Fetch Pending Requests
    context["pending_requests"] = GroupService.get_pending_requests(db, group_id)

    return render_template(
        "group/management_hub.html",
        form=form,
        invite_friend_form=invite_friend_form,
        invite_email_form=invite_email_form,
        **context,
    )


@bp.route(
    "/<string:group_id>/handle_request/<string:request_id>/<string:action>",
    methods=["POST"],
)
@login_required
def handle_membership_request(
    group_id: str,
    request_id: str,
    action: str,
) -> Response | str | dict[str, Any]:
    """Approve or decline a join request."""
    db = firestore.client()
    try:
        GroupService.handle_membership_request(
            db,
            group_id,
            request_id,
            g.user.uid,
            action,
        )
        flash(f"Request {action}d successfully.", "success")
    except AccessDenied:
        flash(GROUP_MESSAGES["ACCESS_DENIED"], "danger")
    except Exception as e:
        flash(COMMON_MESSAGES["GENERIC_ERROR"].format(error=e), "danger")

    return redirect(url_for(".manage_group", group_id=group_id))  # type: ignore


@bp.route("/create", methods=["GET", "POST"])
@login_required
def create_group() -> Response | str | dict[str, Any]:
    """Create a new group."""
    form = GroupForm()
    if form.validate_on_submit():
        db = firestore.client()
        try:
            group_id = GroupService.create_group(
                db,
                g.user.uid,
                form.data,
                form.profile_picture.data,
            )
            flash(GROUP_MESSAGES["CREATE_SUCCESS"], "success")
            return redirect(url_for(".view_group", group_id=group_id))  # type: ignore
        except Exception as e:
            flash(COMMON_MESSAGES["UNEXPECTED_ERROR"].format(error=e), "danger")
    return render_template("create_group.html", form=form)


def _get_group_for_edit(db: Client, group_id: str) -> dict[str, Any]:
    """Fetch group and verify admin permissions."""
    group_ref = db.collection("groups").document(group_id)
    group = group_ref.get()
    if not group.exists:
        msg = "Group not found."
        raise GroupNotFound(msg)

    group_data = group.to_dict() or {}
    group_data["id"] = group.id

    if not GroupService.is_group_admin(group_data, g.user.uid):
        msg = "You do not have permission to edit this group."
        raise AccessDenied(msg)

    return group_data


def _handle_edit_group_form(
    db: Client,
    group_id: str,
    group_data: dict[str, Any],
) -> tuple[GroupForm, Any | None]:
    """Process GroupForm submission for editing."""
    form = GroupForm(data=group_data)
    if form.validate_on_submit():
        try:
            GroupService.update_group(
                db,
                group_id,
                g.user.uid,
                form.data,
                form.profile_picture.data,
            )
            flash(GROUP_MESSAGES["UPDATE_SUCCESS"], "success")
            return form, redirect(url_for(".view_group", group_id=group_id))
        except AccessDenied:
            flash(GROUP_MESSAGES["EDIT_DENIED"], "danger")
            return form, redirect(url_for(".view_group", group_id=group_id))
        except Exception as e:
            flash(COMMON_MESSAGES["UNEXPECTED_ERROR"].format(error=e), "danger")
    return form, None


@bp.route("/<string:group_id>/edit", methods=["GET", "POST"])
@login_required
def edit_group(group_id: str) -> Response | str | dict[str, Any]:
    """Edit a group."""
    db = firestore.client()
    try:
        group_data = _get_group_for_edit(db, group_id)
    except GroupNotFound:
        flash(GROUP_MESSAGES["NOT_FOUND"], "danger")
        return redirect(url_for(".view_groups"))  # type: ignore
    except AccessDenied as e:
        flash(str(e), "danger")
        return redirect(url_for(".view_group", group_id=group_id))  # type: ignore

    form, resp = _handle_edit_group_form(db, group_id, group_data)
    if resp:
        return resp

    return render_template(
        "edit_group.html",
        form=form,
        group=group_data,
        group_id=group_id,
    )


@bp.route("/<string:group_id>/delete", methods=["POST"])
@login_required
def delete_group(group_id: str) -> Response | str | dict[str, Any]:
    """Delete a group."""
    db = firestore.client()
    group_ref = db.collection("groups").document(group_id)
    group = group_ref.get()
    if not group.exists:
        flash(GROUP_MESSAGES["NOT_FOUND"], "danger")
        return redirect(url_for(".view_groups"))  # type: ignore

    group_data = group.to_dict() or {}
    owner_ref = group_data.get("ownerRef")
    if not owner_ref or owner_ref.id != g.user.uid:
        flash(GROUP_MESSAGES["DELETE_DENIED"], "danger")
        return redirect(url_for(".view_group", group_id=group.id))  # type: ignore

    try:
        group_ref.delete()
        flash(GROUP_MESSAGES["DELETE_SUCCESS"], "success")
        return redirect(url_for(".view_groups"))  # type: ignore
    except Exception as e:
        flash(COMMON_MESSAGES["UNEXPECTED_ERROR"].format(error=e), "danger")
        return redirect(url_for(".view_group", group_id=group.id))  # type: ignore


@bp.route("/<string:group_id>/promote/<string:user_id>", methods=["POST"])
@login_required
def promote_member(group_id: str, user_id: str) -> Response | str | dict[str, Any]:
    """Promote a member to admin."""
    db = firestore.client()
    try:
        GroupService.promote_member(db, group_id, user_id, g.user.uid)
        flash(GROUP_MESSAGES["PROMOTED_CAPTAIN"], "success")
    except AccessDenied:
        flash(GROUP_MESSAGES["PROMOTE_DENIED"], "danger")
    except Exception as e:
        flash(COMMON_MESSAGES["GENERIC_ERROR"].format(error=e), "danger")
    return redirect(url_for(".view_group", group_id=group_id))  # type: ignore


@bp.route("/<string:group_id>/demote/<string:user_id>", methods=["POST"])
@login_required
def demote_member(group_id: str, user_id: str) -> Response | str | dict[str, Any]:
    """Demote an admin to member."""
    db = firestore.client()
    try:
        GroupService.demote_member(db, group_id, user_id, g.user.uid)
        flash(GROUP_MESSAGES["REVOKED_CAPTAIN"], "success")
    except AccessDenied:
        flash(GROUP_MESSAGES["DEMOTE_DENIED"], "danger")
    except Exception as e:
        flash(COMMON_MESSAGES["GENERIC_ERROR"].format(error=e), "danger")
    return redirect(url_for(".view_group", group_id=group_id))  # type: ignore


@bp.route("/<string:group_id>/remove/<string:user_id>", methods=["POST"])
@login_required
def remove_member(group_id: str, user_id: str) -> Response | str | dict[str, Any]:
    """Remove a member from the group."""
    db = firestore.client()
    try:
        GroupService.remove_member(db, group_id, user_id, g.user.uid)
        flash(GROUP_MESSAGES["MEMBER_REMOVED"], "success")
    except AccessDenied as e:
        flash(str(e), "danger")
    except Exception as e:
        flash(COMMON_MESSAGES["GENERIC_ERROR"].format(error=e), "danger")
    return redirect(url_for(".view_group", group_id=group_id))  # type: ignore
