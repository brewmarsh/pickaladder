import uuid
from flask import render_template, redirect, url_for, session, flash
from sqlalchemy import or_, case, func
from pickaladder import db
from . import bp
from .forms import FriendGroupForm, InviteFriendForm
from pickaladder.models import FriendGroup, FriendGroupMember, User, Match
from pickaladder.constants import USER_ID
from pickaladder.auth.decorators import login_required


@bp.route("/", methods=["GET"])
@login_required
def view_groups():
    user_id = uuid.UUID(session[USER_ID])
    user = User.query.get(user_id)
    groups = user.group_memberships
    return render_template("groups.html", groups=groups)


@bp.route("/<uuid:group_id>", methods=["GET", "POST"])
@login_required
def view_group(group_id):
    group = FriendGroup.query.get_or_404(group_id)
    user_id = uuid.UUID(session[USER_ID])
    user = User.query.get(user_id)

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
            new_member = FriendGroupMember(group_id=group.id, user_id=friend_id)
            db.session.add(new_member)
            db.session.commit()
            flash("Friend invited successfully.", "success")
            return redirect(url_for("group.view_group", group_id=group.id))
        except Exception as e:
            db.session.rollback()
            flash(f"An unexpected error occurred: {e}", "danger")

    # --- Leaderboard logic ---
    player_score = case(
        (Match.player1_id == User.id, Match.player1_score),
        else_=Match.player2_score,
    )
    leaderboard = (
        db.session.query(
            User.id,
            User.name,
            func.avg(player_score).label("avg_score"),
            func.count(Match.id).label("games_played"),
        )
        .join(Match, or_(User.id == Match.player1_id, User.id == Match.player2_id))
        .filter(User.id.in_(member_ids))
        .filter(Match.player1_id.in_(member_ids))
        .filter(Match.player2_id.in_(member_ids))
        .group_by(User.id, User.name)
        .order_by(func.avg(player_score).desc())
        .all()
    )

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
    form = FriendGroupForm()
    if form.validate_on_submit():
        user_id = uuid.UUID(session[USER_ID])
        try:
            new_group = FriendGroup(name=form.name.data, owner_id=user_id)
            db.session.add(new_group)
            db.session.flush()  # Flush to get the new_group.id

            # Add the owner as the first member
            new_member = FriendGroupMember(group_id=new_group.id, user_id=user_id)
            db.session.add(new_member)

            db.session.commit()
            flash("Group created successfully.", "success")
            return redirect(url_for("group.view_group", group_id=new_group.id))
        except Exception as e:
            db.session.rollback()
            flash(f"An unexpected error occurred: {e}", "danger")
    return render_template("create_group.html", form=form)
