"""Routes for the group blueprint."""

from dataclasses import dataclass

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
from pickaladder.services import group_service
from pickaladder.user.utils import merge_ghost_user

from . import bp
from .forms import GroupForm, InviteByEmailForm, InviteFriendForm

UPSET_THRESHOLD = 0.25
GUEST_USER = {"username": "Guest", "id": "unknown"}


@dataclass
class Pagination:
    """A simple data class to hold pagination data."""

    items: list
    pages: int


# TODO: Add type hints for Agent clarity
@bp.route("/", methods=["GET"])
@login_required
def view_groups():
    """Display a list of public groups and the user's groups."""
    db = firestore.client()
    search_term = request.args.get("search", "")

    # Query for public groups
    public_groups_query = db.collection("groups").where(
        filter=firestore.FieldFilter("is_public", "==", True)
    )
    if search_term:
        public_groups_query = public_groups_query.where(
            filter=firestore.FieldFilter("name", ">=", search_term)
        ).where(filter=firestore.FieldFilter("name", "<=", search_term + "\uf8ff"))
    public_group_docs = list(public_groups_query.limit(20).stream())

    # Get user's groups
    user_ref = db.collection("users").document(g.user["uid"])
    my_groups_query = db.collection("groups").where(
        filter=firestore.FieldFilter("members", "array_contains", user_ref)
    )
    my_group_docs = list(my_groups_query.stream())

    # --- Enrich groups with owner data ---
    all_groups = public_group_docs + my_group_docs
    owner_refs = [
        group.to_dict().get("ownerRef")
        for group in all_groups
        if group.to_dict().get("ownerRef")
    ]
    unique_owner_refs = list({ref for ref in owner_refs if ref})

    owners_data = {}
    if unique_owner_refs:
        owner_docs = db.get_all(unique_owner_refs)
        owners_data = {doc.id: doc.to_dict() for doc in owner_docs if doc.exists}

    # TODO: Add type hints for Agent clarity
    def enrich_group(group_doc):
        """Attach owner data to a group dictionary."""
        group_data = group_doc.to_dict()
        group_data["id"] = group_doc.id  # Add document ID
        owner_ref = group_data.get("ownerRef")
        if owner_ref and owner_ref.id in owners_data:
            group_data["owner"] = owners_data[owner_ref.id]
        else:
            group_data["owner"] = GUEST_USER
        return group_data

    enriched_public_groups = [enrich_group(doc) for doc in public_group_docs]
    enriched_my_groups = [{"group": enrich_group(doc)} for doc in my_group_docs]

    # The template expects a pagination object with an 'items' attribute.
    pagination_obj = Pagination(
        items=enriched_public_groups,
        pages=1,  # Assume a single page for now
    )
    return render_template(
        "groups.html",
        my_groups=enriched_my_groups,
        pagination=pagination_obj,
        search_term=search_term,
    )


# TODO: Add type hints for Agent clarity
@bp.route("/<string:group_id>", methods=["GET", "POST"])
@login_required
def view_group(group_id):
    """Display a single group's page.

    Display a single group's page, including its members, leaderboard, and
    invite form.
    """
    db = firestore.client()
    current_user_id = g.user["uid"]

    details = group_service.get_group_details(db, group_id, current_user_id)
    if not details:
        flash("Group not found.", "danger")
        return redirect(url_for(".view_groups"))

    group_data = details["group_data"]
    user_ref = db.collection("users").document(current_user_id)

    form = InviteFriendForm()
    invite_email_form = InviteByEmailForm()

    # --- Form submissions ---
    if form.validate_on_submit() and "friend" in request.form:
        friend_id = form.friend.data
        friend_ref = db.collection("users").document(friend_id)
        group_ref = db.collection("groups").document(group_id)
        try:
            group_ref.update({"members": firestore.ArrayUnion([friend_ref])})
            flash("Friend invited successfully.", "success")
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")
        return redirect(url_for(".view_group", group_id=group_id))

    if invite_email_form.validate_on_submit() and "email" in request.form:
        try:
            invite_details = group_service.create_email_invite(
                db=db,
                group_id=group_id,
                group_name=group_data.get("name"),
                inviter_id=current_user_id,
                invitee_name=invite_email_form.name.data or "Friend",
                invitee_email=invite_email_form.email.data,
            )

            invite_url = url_for(
                ".handle_invite", token=invite_details["token"], _external=True
            )
            email_data = {
                "to": invite_details["email"],
                "subject": f"Join {group_data.get('name')} on pickaladder!",
                "template": "email/group_invite.html",
                "name": invite_details["name"],
                "group_name": group_data.get("name"),
                "invite_url": invite_url,
                "joke": group_service.get_random_joke(),
            }

            group_service.send_invite_email_background(
                current_app._get_current_object(), db, invite_details["token"], email_data
            )

            flash(f"Invitation is being sent to {invite_details['email']}.", "toast")
        except Exception as e:
            flash(f"An error occurred creating the invitation: {e}", "danger")
        return redirect(url_for(".view_group", group_id=group_id))

    # --- Populate form choices ---
    member_ids = {member["id"] for member in details["members"]}
    friends_query = (
        user_ref.collection("friends")
        .where(filter=firestore.FieldFilter("status", "==", "accepted"))
        .stream()
    )
    friend_ids = {doc.id for doc in friends_query}
    eligible_friend_ids = list(friend_ids - member_ids)

    if eligible_friend_ids:
        eligible_friends_query = (
            db.collection("users")
            .where(filter=firestore.FieldFilter("__name__", "in", eligible_friend_ids))
            .stream()
        )
        form.friend.choices = [
            (friend.id, friend.to_dict().get("name", friend.id))
            for friend in eligible_friends_query
        ]

    return render_template(
        "group.html",
        group=details["group_data"],
        group_id=group_id,
        members=details["members"],
        owner=details["owner"],
        form=form,
        invite_email_form=invite_email_form,
        current_user_id=current_user_id,
        leaderboard=details["leaderboard"],
        pending_members=details["pending_members"],
        is_member=details["is_member"],
        recent_matches=details["recent_matches"],
        best_buds=details["best_buds"],
        team_leaderboard=details["team_leaderboard"],
    )


# TODO: Add type hints for Agent clarity
@bp.route("/create", methods=["GET", "POST"])
@login_required
def create_group():
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
def edit_group(group_id):
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
def resend_invite(token):
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
        "joke": group_service.get_random_joke(),
    }

    group_service.send_invite_email_background(
        current_app._get_current_object(), db, token, email_data
    )
    flash(f"Resending invitation to {data.get('email')}...", "toast")
    return redirect(url_for(".view_group", group_id=group_id))


# TODO: Add type hints for Agent clarity
@bp.route("/<string:group_id>/leaderboard-trend")
@login_required
def view_leaderboard_trend(group_id):
    """Display a trend chart of the group's leaderboard."""
    db = firestore.client()
    group_ref = db.collection("groups").document(group_id)
    group = group_ref.get()
    if not group.exists:
        flash("Group not found.", "danger")
        return redirect(url_for(".view_groups"))

    group_data = group.to_dict()
    group_data["id"] = group.id

    trend_data = group_service.get_leaderboard_trend_data(db, group_id)
    user_stats = group_service.get_user_group_stats(db, group_id, g.user["uid"])

    return render_template(
        "group_leaderboard_trend.html",
        group=group_data,
        trend_data=trend_data,
        user_stats=user_stats,
    )


# TODO: Add type hints for Agent clarity
@bp.route("/invite/<token>/delete", methods=["POST"])
@login_required
def delete_invite(token):
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
def handle_invite(token):
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
            merge_ghost_user(db, user_ref, invite_email)

        # Add user to group
        group_ref.update({"members": firestore.ArrayUnion([user_ref])})
        # Mark invite as used
        invite_ref.update({"used": True, "used_by": g.user["uid"]})

        # Friend other group members
        group_service.friend_group_members(db, group_id, user_ref)

        flash("Welcome to the team!", "success")
        return redirect(url_for(".view_group", group_id=group_id))
    except Exception as e:
        flash(f"An error occurred while joining the group: {e}", "danger")
        return redirect(url_for("auth.login"))


# TODO: Add type hints for Agent clarity
@bp.route("/<string:group_id>/delete", methods=["POST"])
@login_required
def delete_group(group_id):
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
def join_group(group_id):
    """Join a group."""
    db = firestore.client()
    group_ref = db.collection("groups").document(group_id)
    user_ref = db.collection("users").document(g.user["uid"])

    try:
        group_ref.update({"members": firestore.ArrayUnion([user_ref])})
        group_service.friend_group_members(db, group_id, user_ref)
        flash("Successfully joined the group.", "success")
    except Exception as e:
        flash(f"An error occurred while trying to join the group: {e}", "danger")

    return redirect(url_for(".view_group", group_id=group_id))


# TODO: Add type hints for Agent clarity
@bp.route("/<string:group_id>/leave", methods=["POST"])
@login_required
def leave_group(group_id):
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
@bp.route("/<string:group_id>/stats/head_to_head", methods=["GET"])
@login_required
def get_head_to_head_stats(group_id):
    """Return head-to-head stats for two players in a group."""
    player1_id = request.args.get("player1_id")
    player2_id = request.args.get("player2_id")

    if not all([player1_id, player2_id]):
        return {"error": "player1_id and player2_id are required"}, 400

    db = firestore.client()
    stats = group_service.calculate_head_to_head_stats(
        db, group_id, player1_id, player2_id
    )
    return stats
