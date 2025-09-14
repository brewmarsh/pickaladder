import uuid
from flask import render_template, redirect, url_for, session, flash, request
from sqlalchemy import or_, case
from pickaladder import db
from . import bp
from .forms import GroupForm, InviteFriendForm
from .utils import get_group_leaderboard, save_group_picture
from pickaladder.models import Group, GroupMember, User, Friend
from pickaladder.constants import USER_ID
from pickaladder.auth.decorators import login_required


@bp.route("/", methods=["GET"])
@login_required
def view_groups():
    user_id = uuid.UUID(session[USER_ID])
    user = db.session.get(User, user_id)

    search_term = request.args.get("search", "")
    page = request.args.get("page", 1, type=int)

    # Get user's friends' IDs
    friend_ids = [
        f.friend_id
        for f in db.session.query(Friend.friend_id)
        .filter_by(user_id=user_id, status="accepted")
        .all()
    ]

    # Base query for public groups
    query = Group.query.filter(Group.is_public)

    if search_term:
        like_term = f"%{search_term}%"
        query = query.filter(
            or_(
                Group.name.ilike(like_term),
                Group.description.ilike(like_term),
            )
        )

    # Prioritize friends' groups
    query = query.order_by(
        case((Group.owner_id.in_(friend_ids), 0), else_=1), Group.name
    )

    pagination = query.paginate(page=page, per_page=10, error_out=False)

    my_groups = user.group_memberships

    return render_template(
        "groups.html",
        my_groups=my_groups,
        pagination=pagination,
        search_term=search_term,
    )


@bp.route("/<uuid:group_id>", methods=["GET", "POST"])
@login_required
def view_group(group_id):
    group = db.get_or_404(Group, group_id)
    user_id = uuid.UUID(session[USER_ID])
    user = db.session.get(User, user_id)

    # --- Invite form logic ---
    form = InviteFriendForm()
    # Get user's accepted friends
    friend_ids = [
        f.friend_id for f in user.friend_requests_sent if f.status == "accepted"
    ]
    # Get current group members
    member_ids = [m.user_id for m in group.members]
    # Friends who are not already members
    eligible_friends = User.query.filter(
        User.id.in_(friend_ids), User.id.notin_(member_ids)
    ).all()
    form.friend.choices = [(str(f.id), f.name) for f in eligible_friends]

    if form.validate_on_submit():
        try:
            friend_id = uuid.UUID(form.friend.data)
            new_member = GroupMember(group_id=group.id, user_id=friend_id)
            db.session.add(new_member)
            db.session.commit()
            flash("Friend invited successfully.", "success")
            return redirect(url_for("group.view_group", group_id=group.id))
        except Exception as e:
            db.session.rollback()
            flash(f"An unexpected error occurred: {e}", "danger")

    # --- Leaderboard logic ---
    leaderboard = get_group_leaderboard(group_id)

    return render_template(
        "group.html",
        group=group,
        leaderboard=leaderboard,
        form=form,
        current_user_id=user_id,
    )


@bp.route("/create", methods=["GET", "POST"])
@login_required
def create_group():
    form = GroupForm()
    if form.validate_on_submit():
        user_id = uuid.UUID(session[USER_ID])
        try:
            picture_filename, thumbnail_filename = None, None
            if form.profile_picture.data:
                picture_filename, thumbnail_filename = save_group_picture(
                    form.profile_picture.data
                )

            new_group = Group(
                name=form.name.data,
                owner_id=user_id,
                description=form.description.data,
                is_public=form.is_public.data,
                profile_picture_path=picture_filename,
                profile_picture_thumbnail_path=thumbnail_filename,
            )
            db.session.add(new_group)
            db.session.flush()  # Flush to get the new_group.id

            # Add the owner as the first member
            new_member = GroupMember(group_id=new_group.id, user_id=user_id)
            db.session.add(new_member)

            db.session.commit()
            flash("Group created successfully.", "success")
            return redirect(url_for("group.view_group", group_id=new_group.id))
        except Exception as e:
            db.session.rollback()
            flash(f"An unexpected error occurred: {e}", "danger")
    return render_template("create_group.html", form=form)


@bp.route("/<uuid:group_id>/edit", methods=["GET", "POST"])
@login_required
def edit_group(group_id):
    group = db.get_or_404(Group, group_id)
    user_id = uuid.UUID(session[USER_ID])
    if group.owner_id != user_id:
        flash("You do not have permission to edit this group.", "danger")
        return redirect(url_for("group.view_group", group_id=group.id))

    form = GroupForm(obj=group)
    if form.validate_on_submit():
        try:
            group.name = form.name.data
            group.description = form.description.data
            group.is_public = form.is_public.data

            if form.profile_picture.data:
                picture_filename, thumbnail_filename = save_group_picture(
                    form.profile_picture.data
                )
                group.profile_picture_path = picture_filename
                group.profile_picture_thumbnail_path = thumbnail_filename

            db.session.commit()
            flash("Group updated successfully.", "success")
            return redirect(url_for("group.view_group", group_id=group.id))
        except Exception as e:
            db.session.rollback()
            flash(f"An unexpected error occurred: {e}", "danger")

    return render_template("edit_group.html", form=form, group=group)


@bp.route("/<uuid:group_id>/delete", methods=["POST"])
@login_required
def delete_group(group_id):
    group = db.get_or_404(Group, group_id)
    user_id = uuid.UUID(session[USER_ID])
    if group.owner_id != user_id:
        flash("You do not have permission to delete this group.", "danger")
        return redirect(url_for("group.view_group", group_id=group.id))

    try:
        db.session.delete(group)
        db.session.commit()
        flash("Group deleted successfully.", "success")
        return redirect(url_for("group.view_groups"))
    except Exception as e:
        db.session.rollback()
        flash(f"An unexpected error occurred while deleting the group: {e}", "danger")
        return redirect(url_for("group.view_group", group_id=group.id))
