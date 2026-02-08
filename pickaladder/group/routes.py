"""Routes for the group blueprint."""

from __future__ import annotations

import secrets
from typing import Any

from firebase_admin import firestore, storage
from flask import (
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.utils import secure_filename

from pickaladder.auth.decorators import login_required
from pickaladder.group.services.leaderboard import get_group_leaderboard
from pickaladder.group.services.stats import (
    get_head_to_head_stats as get_h2h_stats,
)
from pickaladder.group.services.stats import (
    get_leaderboard_trend_data,
    get_user_group_stats,
)
from pickaladder.group.services.tasks import (
    friend_group_members,
    send_invite_email_background,
)
# Resolved conflict: Imported both service classes and utility functions
from pickaladder.group.services.group_service import (
    AccessDenied,
    GroupNotFound,
    GroupService,
)
from pickaladder.group.utils import get_random_joke
from pickaladder.user.services import UserService

from . import bp
from .forms import GroupForm, InviteByEmailForm, InviteFriendForm

UPSET_THRESHOLD = 0.25
GUEST_USER = {"username": "Guest", "id": "unknown"}
DOUBLES_TEAM_SIZE = 2


# TODO: Add type hints for Agent clarity
@bp.route("/", methods=["GET"])
@login_required
def view_groups() -> Any:
    """Display the user's groups."""
    db = firestore.client()

    # Get user's groups
    user_ref = db.collection("users").document(g.user["uid"])
    my_groups_query = db.collection("groups").where(
        filter=firestore.FieldFilter("members", "array_contains", user_ref)
    )
    my_group_docs = list(my_groups_query.stream())

    # --- Enrich groups with owner data ---
    owner_refs = [
        group.to_dict().get("ownerRef")
        for group in my_group_docs
        if group.to_dict().get("ownerRef")
    ]
    unique_owner_refs = list({ref for ref in owner_refs if ref})

    owners_data = {}
    if unique_owner_refs:
        owner_docs = db.get_all(unique_owner_refs)
        owners_data = {doc.id: doc.to_dict() for doc in owner_docs if doc.exists}

    # TODO: Add type hints for Agent clarity
    def enrich_group(group_doc: Any) -> dict[str, Any]:
        """Attach owner data and user stats to a group dictionary."""
        group_data: dict[str, Any] = group_doc.to_dict()
        group_id = group_doc.id
        group_data["id"] = group_id

        # Member count
        members = group_data.get("members", [])
        group_data["member_count"] = len(members)

        # Current User's Stats for this group
        leaderboard = get_group_leaderboard(group_id)
        current_user_id = g.user["uid"]
        user_entry = next((p for p in leaderboard if p["id"] == current_user_id), None)

        if user_entry:
            group_data["user_rank"] = leaderboard.index(user_entry) + 1
            group_data["user_record"] = (
                f"{user_entry.get('wins', 0)}W - {user_entry.get('losses', 0)}L"
            )
        else:
            group_data["user_rank"] = "N/A"
            group_data["user_record"] = "0W - 0L"

        owner_ref = group_data.get("ownerRef")
        if owner_ref and owner_ref.id in owners_data:
            group_data["owner"] = owners_data[owner_ref.id]
        else:
            group_data["owner"] = GUEST_USER
        return group_data

    enriched_my_groups = [{"group": enrich_group(doc)} for doc in my_group_docs]

    return render_template(
        "groups.html",
        my_groups=enriched_my_groups,
    )


# TODO: Add type hints for Agent clarity
@bp.route("/<string:group_id>", methods=["GET", "POST"])
@login_required
def view_group(group_id: str) -> Any:
    """Display a single group's page."""
    db = firestore.client()
    player_a_id = request.args.get("playerA")
    player_b_id = request.args.get("playerB")

    try:
        context = GroupService.get_group_details(
            db, group_id, g.user["uid"], player_a_id, player_b_id
        )
    except GroupNotFound:
        flash("Group not found.", "danger")
        return redirect(url_for(".view_groups"))
    except AccessDenied:
        flash("You do not have permission to access this group.", "danger")
        return redirect(url_for(".view_groups"))

    # Handle Forms
    form = InviteFriendForm()
    form.friend.choices = [
        (friend.id, friend.to_dict().get("name", friend.id))
        for friend in context["eligible_friends"]
    ]

    if form.validate_on_submit() and "friend" in request.form:
        try:
            GroupService.invite_friend(db, group_id, form.friend.data)
            flash("Friend invited successfully.", "success")
            return redirect(url_for(".view_group", group_id=group_id))
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")

    invite_email_form = InviteByEmailForm()
    if invite_email_form.validate_on_submit() and "email" in request.form:
        try:
            name = invite_email_form.name.data or "Friend"
            email = invite_email_form.email.data
            GroupService.invite_by_email(
                db, group_id, context["group"]["name"], email, name, g.user["uid"]
            )
            flash(f"Invitation is being sent to {email.lower()}.", "toast")
            return redirect(url_for(".view_group", group_id=group_id))
        except Exception as e:
            flash(f"An error occurred creating the invitation: {e}", "danger")

    return render_template(
        "group.html",
        form=form,
        invite_email_form=invite_email_form,
        **context,
    )


# TODO: Add type hints for Agent clarity
@bp.route("/create", methods=["GET", "POST"])
@login_required
def create_group() -> Any:
    """Create a new group."""
    form = GroupForm()
    if form.validate_on_submit():
        db = firestore.client()
        user_ref = db.collection("users").document(g.user["uid"])
        try:
            group_data = {
                "name": form.name.data,
                "description": form.description.data,
                "location": form.location.data,
                "is_public": form.is_public.data,
                "ownerRef": user_ref,
                "members": [user_ref],  # Owner is the first member
                "createdAt": firestore.SERVER_TIMESTAMP,
            }
            timestamp, new_group_ref = db.collection("groups").add(group_data)
            group_id = new_group_ref.id

            profile_picture_file = form.profile_picture.data
            if profile_picture_file:
                try:
                    filename = secure_filename(
                        profile_picture_file.filename or "group_profile.jpg"
                    )
                    bucket = storage.bucket()
                    blob = bucket.blob(f"group_pictures/{group_id}/{filename}")

                    blob.upload_from_file(profile_picture_file)
                    blob.make_public()

                    new_group_ref.update({"profilePictureUrl": blob.public_url})
                except Exception as e:
                    current_app.logger.error(f"Error uploading group image: {e}")
                    flash("Group created, but failed to upload image.", "warning")
                    return redirect(url_for(".view_group", group_id=group_id))

            flash("Group created successfully.", "success")
            return redirect(url_for(".view_group", group_id=group_id))
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")
    return render_template("create_group.html", form=form)


# TODO: Add type hints for Agent clarity
@bp.route("/<string:group_id>/edit", methods=["GET", "POST"])
@login_required
def edit_group(group_id: str) -> Any:
    """Edit a group."""
    db = firestore.client()
    group_ref = db.collection("groups").document(group_id)
    group = group_ref.get()
    if not group.exists:
        flash("Group not found.", "danger")
        return redirect(url_for(".view_groups"))

    group_data = group.to_dict()
    group_data["id"] = group.id
    owner_ref = group_data.get("ownerRef")
    if not owner_ref or owner_ref.id != g.user["uid"]:
        flash("You do not have permission to edit this group.", "danger")
        return redirect(url_for(".view_group", group_id=group.id))

    form = GroupForm(data=group_data)
    if form.validate_on_submit():
        try:
            update_data = {
                "name": form.name.data,
                "description": form.description.data,
                "location": form.location.data,
                "is_public": form.is_public.data,
            }

            profile_picture_file = form.profile_picture.data
            if profile_picture_file:
                filename = secure_filename(
                    profile_picture_file.filename or "group_profile.jpg"
                )
                bucket = storage.bucket()
                blob = bucket.blob(f"group_pictures/{group_id}/{filename}")

                blob.upload_from_file(profile_picture_file)
                blob.make_public()

                update_data["profilePictureUrl"] = blob.public_url

            group_ref.update(update_data)
            flash("Group updated successfully.", "success")
            return redirect(url_for(".view_group", group_id=group.id))
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")

    return render_template(
        "edit_group.html", form=form, group=group_data, group_id=group.id
    )


# TODO: Add type hints for Agent clarity
@bp.route("/invite/<token>/resend", methods=["POST"])
@login_required
def resend_invite(token: str) -> Any:
    """Resend a group invitation."""
    db = firestore.client()
    invite_ref = db.collection("group_invites").document(token)
    invite = invite_ref.get()

    if not invite.exists:
        flash("Invite not found", "danger")
        return redirect(url_for("auth.login"))

    data = invite.to_dict()
    group_id = data.get("group_id")

    # Check permissions
    group_ref = db.collection("groups").document(group_id)
    group = group_ref.get()
    if not group.exists:
        flash("Group not found", "danger")
        return redirect(url_for("auth.login"))

    owner_ref = group.to_dict().get("ownerRef")
    if not owner_ref or owner_ref.id != g.user["uid"]:
        flash("Permission denied", "danger")
        return redirect(url_for(".view_group", group_id=group_id))

    new_email = request.form.get("email")
    if new_email:
        data["email"] = new_email
        invite_ref.update({"email": new_email})

    invite_ref.update({"status": "sending"})

    invite_url = url_for(".handle_invite", token=token, _external=True)
    email_data = {
        "to": data.get("email"),
        "subject": f"Join {group.to_dict().get('name')} on pickaladder!",
        "template": "email/group_invite.html",
        "name": data.get("name"),
        "group_name": group.to_dict().get("name"),
        "invite_url": invite_url,
        "joke": get_random_joke(),
    }

    send_invite_email_background(
        current_app._get_current_object(),  # type: ignore[attr-defined]
        token,
        email_data,
    )
    flash(f"Resending invitation to {data.get('email')}...", "toast")
    return redirect(url_for(".view_group", group_id=group_id))


# TODO: Add type hints for Agent clarity
@bp.route("/<string:group_id>/leaderboard-trend")
@login_required
def view_leaderboard_trend(group_id: str) -> Any:
    """Display a trend chart of the group's leaderboard."""
    db = firestore.client()
    group_ref = db.collection("groups").document(group_id)
    group = group_ref.get()
    if not group.exists:
        flash("Group not found.", "danger")
        return redirect(url_for(".view_groups"))

    group_data = group.to_dict()
    group_data["id"] = group.id

    trend_data = get_leaderboard_trend_data(group_id)
    user_stats = get_user_group_stats(group_id, g.user["uid"])

    return render_template(
        "group_leaderboard_trend.html",
        group=group_data,
        trend_data=trend_data,
        user_stats=user_stats,
    )


# TODO: Add type hints for Agent clarity
@bp.route("/invite/<token>/delete", methods=["POST"])
@login_required
def delete_invite(token: str) -> Any:
    """Delete a pending invitation."""
    db = firestore.client()
    invite_ref = db.collection("group_invites").document(token)
    invite = invite_ref.get()

    if not invite.exists:
        flash("Invite not found", "danger")
        return redirect(url_for("auth.login"))

    group_id = invite.to_dict().get("group_id")
    group_ref = db.collection("groups").document(group_id)
    group = group_ref.get()

    if not group.exists:
        flash("Group not found", "danger")
        return redirect(url_for("auth.login"))

    owner_ref = group.to_dict().get("ownerRef")
    if not owner_ref or owner_ref.id != g.user["uid"]:
        flash("Permission denied", "danger")
        return redirect(url_for(".view_group", group_id=group_id))

    invite_ref.delete()
    flash("Invitation removed.", "success")
    return redirect(url_for(".view_group", group_id=group_id))


# TODO: Add type hints for Agent clarity
@bp.route("/invite/<token>")
@login_required
def handle_invite(token: str) -> Any:
    """Handle an invitation link."""
    db = firestore.client()
    invite_ref = db.collection("group_invites").document(token)
    invite = invite_ref.get()

    if not invite.exists:
        flash("Invalid invitation link.", "danger")
        return redirect(url_for("auth.login"))

    invite_data = invite.to_dict()
    if invite_data.get("used"):
        flash("This invitation has already been used.", "warning")
        return redirect(url_for("auth.login"))

    group_id = invite_data.get("group_id")
    group_ref = db.collection("groups").document(group_id)
    user_ref = db.collection("users").document(g.user["uid"])

    try:
        # Merge ghost user if exists
        invite_email = invite_data.get("email")
        if invite_email:
            UserService.merge_ghost_user(db, user_ref, invite_email)

        # Add user to group
        group_ref.update({"members": firestore.ArrayUnion([user_ref])})
        # Mark invite as used
        invite_ref.update({"used": True, "used_by": g.user["uid"]})

        # Friend other group members
        friend_group_members(db, group_id, user_ref)

        flash("Welcome to the team!", "success")
        return redirect(url_for(".view_group", group_id=group_id))
    except Exception as e:
        flash(f"An error occurred while joining the group: {e}", "danger")
        return redirect(url_for("auth.login"))


# TODO: Add type hints for Agent clarity
@bp.route("/<string:group_id>/delete", methods=["POST"])
@login_required
def delete_group(group_id: str) -> Any:
    """Delete a group."""
    db = firestore.client()
    group_ref = db.collection("groups").document(group_id)
    group = group_ref.get()
    if not group.exists:
        flash("Group not found.", "danger")
        return redirect(url_for(".view_groups"))

    group_data = group.to_dict()
    owner_ref = group_data.get("ownerRef")
    if not owner_ref or owner_ref.id != g.user["uid"]:
        flash("You do not have permission to delete this group.", "danger")
        return redirect(url_for(".view_group", group_id=group.id))

    try:
        group_ref.delete()
        flash("Group deleted successfully.", "success")
        return redirect(url_for(".view_groups"))
    except Exception as e:
        flash(f"An unexpected error occurred: {e}", "danger")
        return redirect(url_for(".view_group", group_id=group.id))


# TODO: Add type hints for Agent clarity
@bp.route("/<string:group_id>/join", methods=["POST"])
@login_required
def join_group(group_id: str) -> Any:
    """Join a group."""
    db = firestore.client()
    group_ref = db.collection("groups").document(group_id)
    user_ref = db.collection("users").document(g.user["uid"])

    try:
        group_ref.update({"members": firestore.ArrayUnion([user_ref])})
        friend_group_members(db, group_id, user_ref)
        flash("Successfully joined the group.", "success")
    except Exception as e:
        flash(f"An error occurred while trying to join the group: {e}", "danger")

    return redirect(url_for(".view_group", group_id=group_id))


# TODO: Add type hints for Agent clarity
@bp.route("/<string:group_id>/leave", methods=["POST"])
@login_required
def leave_group(group_id: str) -> Any:
    """Leave a group."""
    db = firestore.client()
    group_ref = db.collection("groups").document(group_id)
    user_ref = db.collection("users").document(g.user["uid"])

    try:
        group_ref.update({"members": firestore.ArrayRemove([user_ref])})
        flash("You have left the group.", "success")
    except Exception as e:
        flash(f"An error occurred while trying to leave the group: {e}", "danger")

    return redirect(url_for(".view_group", group_id=group_id))


# TODO: Add type hints for Agent clarity
@bp.route("/<string:group_id>/stats/rivalry", methods=["GET"])
@login_required
def get_rivalry_stats(group_id: str) -> Any:
    """Return head-to-head stats for two players in a group."""
    playerA_id = request.args.get("playerA_id")
    playerB_id = request.args.get("playerB_id")

    if not playerA_id or not playerB_id:
        return {"error": "playerA_id and playerB_id are required"}, 400

    stats = get_h2h_stats(group_id, playerA_id, playerB_id)

    return {
        "wins": stats["wins"],
        "losses": stats["losses"],
        "matches": stats["matches"],
        "point_diff": stats["point_diff"],
        "avg_points_scored": stats["avg_points_scored"],
        "partnership_record": stats["partnership_record"],
    }