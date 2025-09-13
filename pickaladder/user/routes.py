import uuid
import os
from flask import (
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    current_app,
    jsonify,
    send_from_directory,
)
from sqlalchemy import or_, and_
from sqlalchemy.orm import aliased
from PIL import Image
from werkzeug.utils import secure_filename

from pickaladder import db
from . import bp
from .forms import UpdateProfileForm
from pickaladder.models import User, Friend, Match
from pickaladder.match.routes import get_player_record
from pickaladder.group.utils import get_group_leaderboard
from pickaladder.constants import (
    USER_ID,
)
from pickaladder.auth.decorators import login_required


@bp.route("/dashboard")
@login_required
def dashboard():
    user_id = uuid.UUID(session[USER_ID])
    user = db.get_or_404(User, user_id)
    form = UpdateProfileForm(obj=user)

    # The template is now a shell, data is fetched by client-side JS
    # But the form needs to be passed for the update profile section
    return render_template("user_dashboard.html", form=form)


@bp.route("/<uuid:user_id>")
@login_required
def view_user(user_id):
    profile_user = db.get_or_404(User, user_id)
    current_user_id = uuid.UUID(session[USER_ID])

    # Get friends
    friends = (
        db.session.query(User)
        .join(Friend, User.id == Friend.friend_id)
        .filter(Friend.user_id == user_id, Friend.status == "accepted")
        .all()
    )

    # Get match history
    matches = (
        Match.query.filter(
            or_(Match.player1_id == user_id, Match.player2_id == user_id)
        )
        .order_by(Match.match_date.desc())
        .all()
    )

    # Check friendship status
    friendship = Friend.query.filter(
        or_(
            (Friend.user_id == current_user_id) & (Friend.friend_id == user_id),
            (Friend.user_id == user_id) & (Friend.friend_id == current_user_id),
        )
    ).first()

    is_friend = friendship is not None and friendship.status == "accepted"
    friend_request_sent = (
        friendship is not None
        and friendship.status == "pending"
        and friendship.user_id == current_user_id
    )

    record = get_player_record(user_id)

    return render_template(
        "user_profile.html",
        profile_user=profile_user,
        friends=friends,
        matches=matches,
        is_friend=is_friend,
        friend_request_sent=friend_request_sent,
        record=record,
    )


@bp.route("/users")
@login_required
def users():
    search_term = request.args.get("search", "")
    page = request.args.get("page", 1, type=int)
    current_user_id = uuid.UUID(session[USER_ID])

    # Aliases for the friends table to distinguish between sent and received requests
    sent_request = aliased(Friend)
    received_request = aliased(Friend)

    # Base query
    query = (
        db.session.query(
            User,
            sent_request.status.label("sent_status"),
            received_request.status.label("received_status"),
        )
        .outerjoin(
            sent_request,
            and_(
                sent_request.user_id == current_user_id,
                sent_request.friend_id == User.id,
            ),
        )
        .outerjoin(
            received_request,
            and_(
                received_request.user_id == User.id,
                received_request.friend_id == current_user_id,
            ),
        )
        .filter(User.id != current_user_id)
    )

    if search_term:
        like_term = f"%{search_term}%"
        query = query.filter(
            or_(
                User.username.ilike(like_term),
                User.name.ilike(like_term),
            )
        )

    pagination = query.order_by(User.username).paginate(
        page=page, per_page=10, error_out=False
    )

    # Find friends of friends, only if there is no search term.
    fof = []
    if not search_term:
        # Get the IDs of the current user's friends
        my_friends_subquery = (
            db.session.query(Friend.friend_id)
            .filter(Friend.user_id == current_user_id, Friend.status == "accepted")
            .subquery()
        )

        # Get the IDs of the friends of the current user's friends
        fof_subquery = (
            db.session.query(Friend.friend_id)
            .filter(
                Friend.user_id.in_(my_friends_subquery.select()),
                Friend.status == "accepted",
            )
            .subquery()
        )

        # Get the User objects for the FoF IDs, excluding the current user and their
        # direct friends
        fof = (
            User.query.filter(User.id.in_(fof_subquery.select()))
            .filter(User.id != current_user_id)
            .filter(~User.id.in_(my_friends_subquery.select()))
            .limit(10)
            .all()
        )

    return render_template(
        "users.html",
        pagination=pagination,
        search_term=search_term,
        fof=fof,
    )


@bp.route("/send_friend_request/<uuid:friend_id>", methods=["POST"])
@login_required
def send_friend_request(friend_id):
    user_id = uuid.UUID(session[USER_ID])
    if user_id == friend_id:
        flash("You cannot send a friend request to yourself.", "danger")
        return redirect(url_for(".users"))

    existing_friendship = Friend.query.filter(
        or_(
            and_(Friend.user_id == user_id, Friend.friend_id == friend_id),
            and_(Friend.user_id == friend_id, Friend.friend_id == user_id),
        )
    ).first()

    if existing_friendship:
        flash("Friend request already sent or you are already friends.", "warning")
        return redirect(url_for(".users"))

    try:
        new_friend_request = Friend(
            user_id=user_id, friend_id=friend_id, status="pending"
        )
        db.session.add(new_friend_request)
        db.session.commit()
        flash("Friend request sent.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred: {e}", "danger")
    return redirect(url_for(".users"))


@bp.route("/friends")
@login_required
def friends():
    user_id = uuid.UUID(session[USER_ID])

    # Get accepted friends
    friends = (
        db.session.query(User)
        .join(Friend, User.id == Friend.friend_id)
        .filter(Friend.user_id == user_id, Friend.status == "accepted")
        .all()
    )

    # Get pending friend requests received
    requests = (
        db.session.query(User)
        .join(Friend, User.id == Friend.user_id)
        .filter(Friend.friend_id == user_id, Friend.status == "pending")
        .all()
    )

    # Get pending friend requests sent
    sent_requests = (
        db.session.query(User)
        .join(Friend, User.id == Friend.friend_id)
        .filter(Friend.user_id == user_id, Friend.status == "pending")
        .all()
    )

    return render_template(
        "friends.html",
        friends=friends,
        requests=requests,
        sent_requests=sent_requests,
    )


@bp.route("/accept_friend_request/<uuid:friend_id>", methods=["POST"])
@login_required
def accept_friend_request(friend_id):
    user_id = uuid.UUID(session[USER_ID])
    try:
        # The friend request is from friend_id to user_id
        request_to_accept = db.session.get(Friend, (friend_id, user_id))
        if not request_to_accept:
            flash("Friend request not found.", "danger")
            return redirect(url_for(".friends"))

        request_to_accept.status = "accepted"

        # Create the reciprocal friendship
        reciprocal_friendship = Friend(
            user_id=user_id, friend_id=friend_id, status="accepted"
        )
        db.session.add(reciprocal_friendship)
        db.session.commit()
        flash("Friend request accepted.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred: {e}", "danger")

    return redirect(url_for(".friends"))


@bp.route("/decline_friend_request/<uuid:friend_id>", methods=["POST"])
@login_required
def decline_friend_request(friend_id):
    user_id = uuid.UUID(session[USER_ID])
    try:
        request_to_decline = db.session.get(Friend, (friend_id, user_id))
        if request_to_decline:
            db.session.delete(request_to_decline)
            db.session.commit()
            flash("Friend request declined.", "success")
        else:
            flash("Friend request not found.", "danger")
    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred: {e}", "danger")

    return redirect(url_for(".friends"))


@bp.route("/profile_picture/<uuid:user_id>")
def profile_picture(user_id):
    user = db.get_or_404(User, user_id)
    if user.profile_picture_path:
        return send_from_directory(
            current_app.config["UPLOAD_FOLDER"], user.profile_picture_path
        )
    return redirect(url_for("static", filename="user_icon.png"))


@bp.route("/profile_picture_thumbnail/<uuid:user_id>")
def profile_picture_thumbnail(user_id):
    user = db.get_or_404(User, user_id)
    if user.profile_picture_thumbnail_path:
        return send_from_directory(
            current_app.config["UPLOAD_FOLDER"], user.profile_picture_thumbnail_path
        )
    return redirect(url_for("static", filename="user_icon.png"))


@bp.route("/update_profile", methods=["POST"])
@login_required
def update_profile():
    user_id = uuid.UUID(session[USER_ID])
    user = db.get_or_404(User, user_id)
    form = UpdateProfileForm()

    if form.validate_on_submit():
        try:
            user.dark_mode = form.dark_mode.data
            if form.dupr_rating.data is not None:
                user.dupr_rating = form.dupr_rating.data

            profile_picture_file = form.profile_picture.data
            if profile_picture_file:
                # The FileAllowed validator already checked the extension
                if len(profile_picture_file.read()) > 10 * 1024 * 1024:  # 10MB max size
                    flash("Profile picture is too large (max 10MB).", "danger")
                    return redirect(url_for(".dashboard"))

                profile_picture_file.seek(0)
                img = Image.open(profile_picture_file)

                unique_id = uuid.uuid4().hex
                filename = secure_filename(f"{unique_id}_profile.png")
                thumbnail_filename = secure_filename(f"{unique_id}_thumbnail.png")

                upload_folder = current_app.config["UPLOAD_FOLDER"]
                if not os.path.exists(upload_folder):
                    os.makedirs(upload_folder)

                img.thumbnail((512, 512))
                filepath = os.path.join(upload_folder, filename)
                img.save(filepath, format="PNG")
                user.profile_picture_path = filename

                img.thumbnail((64, 64))
                thumbnail_filepath = os.path.join(upload_folder, thumbnail_filename)
                img.save(thumbnail_filepath, format="PNG")
                user.profile_picture_thumbnail_path = thumbnail_filename

                current_app.logger.info(
                    f"User {user_id} updated their profile picture."
                )

            db.session.commit()
            flash("Profile updated successfully.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred: {e}", "danger")
    else:
        # If the form is invalid, flash the errors
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in {getattr(form, field).label.text}: {error}", "danger")

    return redirect(url_for(".dashboard"))


@bp.route("/api/dashboard")
@login_required
def api_dashboard():
    user_id = uuid.UUID(session[USER_ID])
    user = db.get_or_404(User, user_id)

    # Get accepted friends
    friends = (
        db.session.query(User)
        .join(Friend, User.id == Friend.friend_id)
        .filter(Friend.user_id == user_id, Friend.status == "accepted")
        .all()
    )

    # Get pending friend requests
    requests = (
        db.session.query(User)
        .join(Friend, User.id == Friend.user_id)
        .filter(Friend.friend_id == user_id, Friend.status == "pending")
        .all()
    )

    # Get match history
    matches = (
        Match.query.filter(
            or_(Match.player1_id == user_id, Match.player2_id == user_id)
        )
        .order_by(Match.match_date.desc())
        .limit(10)
        .all()
    )

    # Prepare data for JSON response
    user_data = {
        "id": str(user.id),
        "name": user.name,
        "username": user.username,
        "email": user.email,
        "dupr_rating": str(user.dupr_rating) if user.dupr_rating else None,
    }
    friends_data = [
        {
            "id": str(f.id),
            "username": f.username,
            "dupr_rating": str(f.dupr_rating) if f.dupr_rating else None,
        }
        for f in friends
    ]
    requests_data = []
    for r in requests:
        requests_data.append(
            {
                "id": str(r.id),
                "username": r.username,
                "thumbnail_url": url_for(
                    "user.profile_picture_thumbnail", user_id=r.id
                ),
            }
        )
    matches_data = []
    for match in matches:
        opponent = match.player2 if match.player1_id == user_id else match.player1
        matches_data.append(
            {
                "id": str(match.id),
                "opponent_username": opponent.username,
                "opponent_id": str(opponent.id),
                "user_score": (
                    match.player1_score
                    if match.player1_id == user_id
                    else match.player2_score
                ),
                "opponent_score": (
                    match.player2_score
                    if match.player1_id == user_id
                    else match.player1_score
                ),
                "date": (
                    match.match_date.strftime("%Y-%m-%d") if match.match_date else None
                ),
            }
        )

    # Get group rankings
    group_rankings = []
    for membership in user.group_memberships:
        group = membership.group
        leaderboard = get_group_leaderboard(group.id)
        rank = "N/A"
        for i, player in enumerate(leaderboard):
            if player.id == user_id:
                rank = i + 1
                break
        group_rankings.append(
            {
                "group_id": str(group.id),
                "group_name": group.name,
                "rank": rank,
            }
        )

    return jsonify(
        {
            "user": user_data,
            "friends": friends_data,
            "requests": requests_data,
            "matches": matches_data,
            "group_rankings": group_rankings,
        }
    )
