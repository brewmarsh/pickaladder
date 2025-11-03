"""Routes for the group blueprint."""

from dataclasses import dataclass

from firebase_admin import firestore
from flask import flash, g, redirect, render_template, request, url_for

from pickaladder.auth.decorators import login_required

from . import bp
from .forms import GroupForm, InviteFriendForm


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
    """Display a single group's page, including its members, leaderboard, and invite form."""
    db = firestore.client()
    group_ref = db.collection("groups").document(group_id)
    group = group_ref.get()
    if not group.exists:
        flash("Group not found.", "danger")
        return redirect(url_for(".view_groups"))

    group_data = group.to_dict()
    current_user_id = g.user["uid"]
    user_ref = db.collection("users").document(current_user_id)

    # Fetch members' data
    member_refs = group_data.get("members", [])
    member_ids = {ref.id for ref in member_refs}
    members = [ref.get() for ref in member_refs]

    # Fetch owner's data
    owner = None
    owner_ref = group_data.get("ownerRef")
    if owner_ref:
        owner_doc = owner_ref.get()
        if owner_doc.exists:
            owner = owner_doc.to_dict()

    # --- Invite form logic ---
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

    if form.validate_on_submit():
        friend_id = form.friend.data
        friend_ref = db.collection("users").document(friend_id)
        try:
            group_ref.update({"members": firestore.ArrayUnion([friend_ref])})
            flash("Friend invited successfully.", "success")
            return redirect(url_for(".view_group", group_id=group_id))
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")

    return render_template(
        "group.html",
        group=group_data,
        group_id=group.id,
        members=members,
        owner=owner,
        form=form,
        current_user_id=current_user_id,
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
                "is_public": form.is_public.data,
                "ownerRef": user_ref,
                "members": [user_ref],  # Owner is the first member
                "createdAt": firestore.SERVER_TIMESTAMP,
            }
            timestamp, new_group_ref = db.collection("groups").add(group_data)
            flash("Group created successfully.", "success")
            return redirect(url_for(".view_group", group_id=new_group_ref.id))
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
    owner_ref = group_data.get("ownerRef")
    if not owner_ref or owner_ref.id != g.user["uid"]:
        flash("You do not have permission to edit this group.", "danger")
        return redirect(url_for(".view_group", group_id=group.id))

    form = GroupForm(data=group_data)
    if form.validate_on_submit():
        try:
            group_ref.update(
                {
                    "name": form.name.data,
                    "description": form.description.data,
                    "is_public": form.is_public.data,
                }
            )
            flash("Group updated successfully.", "success")
            return redirect(url_for(".view_group", group_id=group.id))
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")

    return render_template(
        "edit_group.html", form=form, group=group_data, group_id=group.id
    )


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
