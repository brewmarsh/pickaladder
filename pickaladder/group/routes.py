"""Routes for the group blueprint."""

import secrets
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
from pickaladder.group.utils import (
    friend_group_members,
    get_group_leaderboard,
    get_leaderboard_trend_data,
    get_random_joke,
    get_user_group_stats,
    send_invite_email_background,
)
from pickaladder.user.utils import merge_ghost_user

from . import bp
from .forms import GroupForm, InviteByEmailForm, InviteFriendForm


@dataclass
class Pagination:
    """A simple data class to hold pagination data."""

    items: list
    pages: int


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

    def enrich_group(group_doc):
        """Attach owner data to a group dictionary."""
        group_data = group_doc.to_dict()
        group_data["id"] = group_doc.id  # Add document ID
        owner_ref = group_data.get("ownerRef")
        if owner_ref and owner_ref.id in owners_data:
            group_data["owner"] = owners_data[owner_ref.id]
        else:
            group_data["owner"] = {"username": "Unknown"}
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


@bp.route("/<string:group_id>", methods=["GET", "POST"])
@login_required
def view_group(group_id):
    """Display a single group's page.

    Display a single group's page, including its members, leaderboard, and
    invite form.
    """
    db = firestore.client()
    group_ref = db.collection("groups").document(group_id)
    group = group_ref.get()
    if not group.exists:
        flash("Group not found.", "danger")
        return redirect(url_for(".view_groups"))

    group_data = group.to_dict()
    group_data["id"] = group.id
    current_user_id = g.user["uid"]
    user_ref = db.collection("users").document(current_user_id)

    # Fetch members' data
    member_refs = group_data.get("members", [])
    member_ids = {ref.id for ref in member_refs}
    members_snapshots = [ref.get() for ref in member_refs]
    members = []
    for snapshot in members_snapshots:
        if snapshot.exists:
            data = snapshot.to_dict()
            data["id"] = snapshot.id
            members.append(data)

    # Fetch owner's data
    owner = None
    owner_ref = group_data.get("ownerRef")
    if owner_ref:
        owner_doc = owner_ref.get()
        if owner_doc.exists:
            owner = owner_doc.to_dict()

    # --- Leaderboard ---
    leaderboard = get_group_leaderboard(group_id)

    is_member = current_user_id in member_ids

    # --- Fetch Pending Invites ---
    pending_members = []
    if is_member:
        invites_ref = db.collection("group_invites")
        query = invites_ref.where(
            filter=firestore.FieldFilter("group_id", "==", group_id)
        ).where(filter=firestore.FieldFilter("used", "==", False))

        pending_invites_docs = list(query.stream())
        for doc in pending_invites_docs:
            data = doc.to_dict()
            data["token"] = doc.id
            pending_members.append(data)

        # Enrich invites with user data
        invite_emails = [
            invite.get("email") for invite in pending_members if invite.get("email")
        ]
        if invite_emails:
            user_docs = {}
            # Chunk the email list to handle Firestore's 30-item limit for 'in' queries
            for i in range(0, len(invite_emails), 30):
                chunk = invite_emails[i : i + 30]
                users_ref = db.collection("users")
                user_query = users_ref.where(
                    filter=firestore.FieldFilter("email", "in", chunk)
                )
                for doc in user_query.stream():
                    user_docs[doc.to_dict()["email"]] = doc.to_dict()

            for invite in pending_members:
                user_data = user_docs.get(invite.get("email"))
                if user_data:
                    invite["username"] = user_data.get("username", invite.get("name"))
                    invite["profilePictureUrl"] = user_data.get("profilePictureUrl")

        # Sort in memory to avoid composite index requirement
        pending_members.sort(key=lambda x: x.get("created_at") or 0, reverse=True)
    form = InviteFriendForm()

    # Get user's accepted friends
    friends_query = (
        user_ref.collection("friends")
        .where(filter=firestore.FieldFilter("status", "==", "accepted"))
        .stream()
    )
    friend_ids = {doc.id for doc in friends_query}

    # Find friends who are not already members
    eligible_friend_ids = list(friend_ids - member_ids)

    eligible_friends = []
    if eligible_friend_ids:
        eligible_friends_query = (
            db.collection("users")
            .where(filter=firestore.FieldFilter("__name__", "in", eligible_friend_ids))
            .stream()
        )
        eligible_friends = [doc for doc in eligible_friends_query]

    form.friend.choices = [
        (friend.id, friend.to_dict().get("name", friend.id))
        for friend in eligible_friends
    ]

    if form.validate_on_submit() and "friend" in request.form:
        friend_id = form.friend.data
        friend_ref = db.collection("users").document(friend_id)
        try:
            group_ref.update({"members": firestore.ArrayUnion([friend_ref])})
            flash("Friend invited successfully.", "success")
            return redirect(url_for(".view_group", group_id=group_id))
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")

    # --- Invite by Email Logic ---
    invite_email_form = InviteByEmailForm()
    if invite_email_form.validate_on_submit() and "email" in request.form:
        try:
            name = invite_email_form.name.data or "Friend"
            original_email = invite_email_form.email.data
            email = original_email.lower()

            # Check if user exists (checking both original and lowercase to be safe)
            users_ref = db.collection("users")
            existing_user = None

            # 1. Check lowercase
            query_lower = users_ref.where(
                filter=firestore.FieldFilter("email", "==", email)
            ).limit(1)
            docs = list(query_lower.stream())

            if docs:
                existing_user = docs[0]
            else:
                # 2. Check original if different
                if original_email != email:
                    query_orig = users_ref.where(
                        filter=firestore.FieldFilter("email", "==", original_email)
                    ).limit(1)
                    docs = list(query_orig.stream())
                    if docs:
                        existing_user = docs[0]

            if existing_user:
                # User exists, use their stored email for the invite to ensure
                # matching works
                invite_email = existing_user.to_dict().get("email")
            else:
                # User does not exist, create a Ghost User This allows matches to
                # be recorded against them before they register
                invite_email = email
                ghost_user_data = {
                    "email": email,
                    "name": name,
                    "is_ghost": True,
                    "createdAt": firestore.SERVER_TIMESTAMP,
                    # Add a unique username-like field to avoid potential issues
                    # if code relies on it
                    "username": f"ghost_{secrets.token_hex(4)}",
                }
                # Let Firestore auto-generate the ID
                db.collection("users").add(ghost_user_data)

            token = secrets.token_urlsafe(32)
            invite_data = {
                "group_id": group_id,
                "email": invite_email,
                "name": name,
                "inviter_id": current_user_id,
                "created_at": firestore.SERVER_TIMESTAMP,
                "used": False,
                "status": "sending",
            }
            db.collection("group_invites").document(token).set(invite_data)

            invite_url = url_for(".handle_invite", token=token, _external=True)
            email_data = {
                "to": email,
                "subject": f"Join {group_data.get('name')} on pickaladder!",
                "template": "email/group_invite.html",
                "name": name,
                "group_name": group_data.get("name"),
                "invite_url": invite_url,
                "joke": get_random_joke(),
            }

            send_invite_email_background(
                current_app._get_current_object(), token, email_data
            )

            flash(f"Invitation is being sent to {email}.", "toast")
            return redirect(url_for(".view_group", group_id=group_id))
        except Exception as e:
            flash(f"An error occurred creating the invitation: {e}", "danger")

    # --- Leaderboard ---
    leaderboard = get_group_leaderboard(group_id)

    is_member = current_user_id in member_ids

    return render_template(
        "group.html",
        group=group_data,
        group_id=group.id,
        members=members,
        owner=owner,
        form=form,
        invite_email_form=invite_email_form,
        current_user_id=current_user_id,
        leaderboard=leaderboard,
        pending_members=pending_members,
        is_member=is_member,
    )


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
        "joke": get_random_joke(),
    }

    send_invite_email_background(current_app._get_current_object(), token, email_data)
    flash(f"Resending invitation to {data.get('email')}...", "toast")
    return redirect(url_for(".view_group", group_id=group_id))


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

    trend_data = get_leaderboard_trend_data(group_id)
    user_stats = get_user_group_stats(group_id, g.user["uid"])

    return render_template(
        "group_leaderboard_trend.html",
        group=group_data,
        trend_data=trend_data,
        user_stats=user_stats,
    )


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
        friend_group_members(db, group_id, user_ref)

        flash("Welcome to the team!", "success")
        return redirect(url_for(".view_group", group_id=group_id))
    except Exception as e:
        flash(f"An error occurred while joining the group: {e}", "danger")
        return redirect(url_for("auth.login"))


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


@bp.route("/<string:group_id>/join", methods=["POST"])
@login_required
def join_group(group_id):
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
