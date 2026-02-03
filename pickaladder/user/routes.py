"""Routes for the user blueprint."""

import datetime
import os
import secrets
import tempfile

from firebase_admin import auth, firestore, storage
from flask import (
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.utils import secure_filename

from pickaladder.auth.decorators import login_required
from pickaladder.utils import EmailError, send_email

from . import bp
from .forms import UpdateProfileForm, UpdateUserForm
from .utils import UserService


class MockPagination:
    """A mock pagination object."""

    # TODO: Add type hints for Agent clarity
    def __init__(self, items):
        """Initialize the mock pagination object."""
        self.items = items
        self.pages = 1


# TODO: Add type hints for Agent clarity
@bp.route("/edit_profile", methods=["GET", "POST"])
@login_required
def edit_profile():
    """Handle user profile updates for name, username, and email."""
    db = firestore.client()
    user_id = g.user["uid"]
    user_ref = db.collection("users").document(user_id)
    user_data = g.user
    form = UpdateUserForm(data=user_data)

    if form.validate_on_submit():
        new_email = form.email.data
        new_username = form.username.data
        update_data = {
            "name": form.name.data,
            "username": new_username,
        }

        # Handle username change
        if new_username != user_data.get("username"):
            users_ref = db.collection("users")
            existing_user = (
                users_ref.where(
                    filter=firestore.FieldFilter("username", "==", new_username)
                )
                .limit(1)
                .stream()
            )
            if len(list(existing_user)) > 0:
                flash(
                    "Username already exists. Please choose a different one.", "danger"
                )
                return render_template("edit_profile.html", form=form, user=user_data)

        # Handle email change
        if new_email != user_data.get("email"):
            try:
                auth.update_user(user_id, email=new_email, email_verified=False)
                verification_link = auth.generate_email_verification_link(new_email)
                send_email(
                    to=new_email,
                    subject="Verify Your New Email Address",
                    template="email/verify_email.html",
                    user={"username": new_username},
                    verification_link=verification_link,
                )
                update_data["email"] = new_email
                update_data["email_verified"] = False
                flash(
                    "Your email has been updated. Please check your new email "
                    "address to verify it.",
                    "info",
                )
            except auth.EmailAlreadyExistsError:
                flash("That email address is already in use.", "danger")
                return render_template("edit_profile.html", form=form, user=user_data)
            except EmailError as e:
                current_app.logger.error(f"Email error updating email: {e}")
                flash(str(e), "danger")
                return render_template("edit_profile.html", form=form, user=user_data)
            except Exception as e:
                current_app.logger.error(f"Error updating email: {e}")
                flash("An error occurred while updating your email.", "danger")
                return render_template("edit_profile.html", form=form, user=user_data)

        if update_data:
            user_ref.update(update_data)
            flash("Account updated successfully.", "success")
        return redirect(url_for(".edit_profile"))

    return render_template("edit_profile.html", form=form, user=user_data)


# TODO: Add type hints for Agent clarity
@bp.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    """Render the user dashboard and handles profile updates.

    On GET, it displays the dashboard with the profile form.
    On POST, it processes the profile update form.
    """
    db = firestore.client()
    user_id = g.user["uid"]
    user_ref = db.collection("users").document(user_id)
    user_data = g.user

    form = UpdateProfileForm()
    if request.method == "GET":
        form.dupr_rating.data = user_data.get("duprRating")
        form.dark_mode.data = user_data.get("dark_mode")

    if form.validate_on_submit():
        try:
            update_data = {
                "dark_mode": bool(form.dark_mode.data),
            }
            if form.dupr_rating.data is not None:
                update_data["duprRating"] = float(form.dupr_rating.data)

            profile_picture_file = form.profile_picture.data
            if profile_picture_file:
                filename = secure_filename(
                    profile_picture_file.filename or "profile.jpg"
                )
                bucket = storage.bucket()
                blob = bucket.blob(f"profile_pictures/{user_id}/{filename}")

                with tempfile.NamedTemporaryFile(
                    suffix=os.path.splitext(filename)[1]
                ) as temp_file:
                    profile_picture_file.save(temp_file.name)
                    blob.upload_from_filename(temp_file.name)

                blob.make_public()
                update_data["profilePictureUrl"] = blob.public_url

            user_ref.update(update_data)
            flash("Profile updated successfully.", "success")
            return redirect(url_for(".dashboard"))
        except Exception as e:
            current_app.logger.error(f"Error updating profile: {e}")
            flash(f"An error occurred: {e}", "danger")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in {getattr(form, field).label.text}: {error}", "danger")

    return render_template("user_dashboard.html", form=form, user=user_data)


# TODO: Add type hints for Agent clarity
@bp.route("/<string:user_id>")
@login_required
def view_user(user_id):
    """Display a user's public profile."""
    db = firestore.client()
    profile_user_data = UserService.get_user_by_id(db, user_id)

    if not profile_user_data:
        flash("User not found.", "danger")
        return redirect(url_for(".users"))

    current_user_id = g.user["uid"]

    # Fetch friendship status
    is_friend, friend_request_sent = UserService.get_friendship_info(
        db, current_user_id, user_id
    )

    # H2H STATS
    h2h_stats = None
    if current_user_id != user_id:
        h2h_stats = UserService.get_h2h_stats(db, current_user_id, user_id)

    # Fetch user's friends (limited for display)
    friends = UserService.get_user_friends(db, user_id, limit=10)

    # Fetch and process user's match history
    matches = UserService.get_user_matches(db, user_id)
    stats = UserService.calculate_stats(matches, user_id)

    # Format matches for display
    display_items = stats["processed_matches"][:20]
    final_matches = UserService.format_matches_for_profile(
        db, display_items, user_id, profile_user_data
    )

    return render_template(
        "user_profile.html",
        profile_user=profile_user_data,
        friends=friends,
        matches=final_matches,
        is_friend=is_friend,
        friend_request_sent=friend_request_sent,
        record={"wins": stats["wins"], "losses": stats["losses"]},
        user=g.user,
        total_games=stats["total_games"],
        win_rate=stats["win_rate"],
        current_streak=stats["current_streak"],
        streak_type=stats["streak_type"],
        h2h_stats=h2h_stats,
    )


# TODO: Add type hints for Agent clarity
@bp.route("/users")
@login_required
def users():
    """List and allows searching for users."""
    db = firestore.client()
    current_user_id = g.user["uid"]
    search_term = request.args.get("search", "")
    query = db.collection("users")

    if search_term:
        # Firestore doesn't support case-insensitive search natively.
        # This searches for an exact username match.
        query = query.where(
            filter=firestore.FieldFilter("username", ">=", search_term)
        ).where(filter=firestore.FieldFilter("username", "<=", search_term + "\uf8ff"))

    all_users_docs = [
        doc for doc in query.limit(20).stream() if doc.id != current_user_id
    ]

    # Get all friend relationships for the current user to check status efficiently
    friends_ref = db.collection("users").document(current_user_id).collection("friends")
    friends_docs = friends_ref.stream()
    friend_statuses = {doc.id: doc.to_dict() for doc in friends_docs}

    user_items = []
    for user_doc in all_users_docs:
        user_data = user_doc.to_dict()
        user_data["id"] = user_doc.id  # Add document ID to the dictionary

        sent_status = None
        received_status = None

        friend_data = friend_statuses.get(user_doc.id)
        if friend_data:
            status = friend_data.get("status")
            initiator = friend_data.get("initiator")

            if initiator:
                sent_status = status
            else:
                received_status = status

        user_items.append((user_data, sent_status, received_status))

    # The template expects a pagination object with an 'items' attribute.
    # We are not implementing full pagination, just adapting to the template.
    pagination = MockPagination(user_items)

    # The template also iterates over 'fof' (friends of friends)
    fof = []

    return render_template(
        "users.html", pagination=pagination, search_term=search_term, fof=fof
    )


# TODO: Add type hints for Agent clarity
@bp.route("/send_friend_request/<string:friend_id>", methods=["POST"])
@login_required
def send_friend_request(friend_id):
    """Send a friend request to another user."""
    db = firestore.client()
    current_user_id = g.user["uid"]
    if current_user_id == friend_id:
        flash("You cannot send a friend request to yourself.", "danger")
        return redirect(url_for(".users"))

    # Use a batch to ensure both documents are created or neither is.
    batch = db.batch()

    # Create pending request in current user's friend list
    my_friend_ref = (
        db.collection("users")
        .document(current_user_id)
        .collection("friends")
        .document(friend_id)
    )
    batch.set(my_friend_ref, {"status": "pending", "initiator": True})

    # Create pending request in target user's friend list
    their_friend_ref = (
        db.collection("users")
        .document(friend_id)
        .collection("friends")
        .document(current_user_id)
    )
    batch.set(their_friend_ref, {"status": "pending", "initiator": False})

    try:
        batch.commit()
        flash("Friend request sent.", "success")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"success": True})
    except Exception as e:
        current_app.logger.error(f"Error sending friend request: {e}")
        flash("An error occurred while sending the friend request.", "danger")
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"success": False, "message": str(e)})

    return redirect(url_for(".users"))


# TODO: Add type hints for Agent clarity
@bp.route("/friends")
@login_required
def friends():
    """Display the user's friends and pending requests."""
    db = firestore.client()
    current_user_id = g.user["uid"]
    friends_ref = db.collection("users").document(current_user_id).collection("friends")

    # Fetch accepted friends
    accepted_docs = friends_ref.where(
        filter=firestore.FieldFilter("status", "==", "accepted")
    ).stream()
    accepted_ids = [doc.id for doc in accepted_docs]
    accepted_friends = []
    if accepted_ids:
        refs = [db.collection("users").document(uid) for uid in accepted_ids]
        docs = db.get_all(refs)
        accepted_friends = [
            {"id": doc.id, **doc.to_dict()} for doc in docs if doc.exists
        ]

    # Fetch pending requests (where the other user was the initiator)
    requests_docs = (
        friends_ref.where(filter=firestore.FieldFilter("status", "==", "pending"))
        .where(filter=firestore.FieldFilter("initiator", "==", False))
        .stream()
    )
    request_ids = [doc.id for doc in requests_docs]
    pending_requests = []
    if request_ids:
        refs = [db.collection("users").document(uid) for uid in request_ids]
        docs = db.get_all(refs)
        pending_requests = [
            {"id": doc.id, **doc.to_dict()} for doc in docs if doc.exists
        ]

    # Fetch sent requests (where the current user was the initiator)
    sent_docs = (
        friends_ref.where(filter=firestore.FieldFilter("status", "==", "pending"))
        .where(filter=firestore.FieldFilter("initiator", "==", True))
        .stream()
    )
    sent_ids = [doc.id for doc in sent_docs]
    sent_requests = []
    if sent_ids:
        refs = [db.collection("users").document(uid) for uid in sent_ids]
        docs = db.get_all(refs)
        sent_requests = [{"id": doc.id, **doc.to_dict()} for doc in docs if doc.exists]

    return render_template(
        "friends/index.html",
        friends=accepted_friends,
        requests=pending_requests,
        sent_requests=sent_requests,
    )


# TODO: Add type hints for Agent clarity
@bp.route("/accept_friend_request/<string:friend_id>", methods=["POST"])
@login_required
def accept_friend_request(friend_id):
    """Accept a friend request."""
    db = firestore.client()
    current_user_id = g.user["uid"]
    batch = db.batch()

    # Update status in current user's friend list
    my_friend_ref = (
        db.collection("users")
        .document(current_user_id)
        .collection("friends")
        .document(friend_id)
    )
    batch.update(my_friend_ref, {"status": "accepted"})

    # Update status in the other user's friend list
    their_friend_ref = (
        db.collection("users")
        .document(friend_id)
        .collection("friends")
        .document(current_user_id)
    )
    batch.update(their_friend_ref, {"status": "accepted"})

    try:
        batch.commit()
        flash("Friend request accepted.", "success")
    except Exception as e:
        current_app.logger.error(f"Error accepting friend request: {e}")
        flash("An error occurred while accepting the request.", "danger")

    return redirect(url_for(".friends"))


# TODO: Add type hints for Agent clarity
@bp.route("/decline_friend_request/<string:friend_id>", methods=["POST"])
@login_required
def decline_friend_request(friend_id):
    """Decline a friend request."""
    db = firestore.client()
    current_user_id = g.user["uid"]
    batch = db.batch()

    # Delete request from current user's list
    my_friend_ref = (
        db.collection("users")
        .document(current_user_id)
        .collection("friends")
        .document(friend_id)
    )
    batch.delete(my_friend_ref)

    # Delete request from the other user's list
    their_friend_ref = (
        db.collection("users")
        .document(friend_id)
        .collection("friends")
        .document(current_user_id)
    )
    batch.delete(their_friend_ref)

    try:
        batch.commit()
        flash("Friend request declined.", "success")
    except Exception as e:
        current_app.logger.error(f"Error declining friend request: {e}")
        flash("An error occurred while declining the request.", "danger")

    return redirect(url_for(".friends"))


# TODO: Add type hints for Agent clarity
@bp.route("/api/dashboard")
@login_required
def api_dashboard():
    """Provide dashboard data as JSON, including matches and group rankings."""
    db = firestore.client()
    user_id = g.user["uid"]
    user_data = UserService.get_user_by_id(db, user_id)

    # Fetch friends
    friends_data = UserService.get_user_friends(db, user_id)

    # Fetch pending friend requests
    requests_data = UserService.get_user_pending_requests(db, user_id)

    # Fetch and process matches
    matches = UserService.get_user_matches(db, user_id)
    stats = UserService.calculate_stats(matches, user_id)

    # Sort all match docs by date and take the most recent 10 for the feed
    sorted_matches_docs = sorted(
        matches,
        key=lambda x: x.to_dict().get("matchDate") or x.create_time,
        reverse=True,
    )[:10]

    # Format matches for the dashboard feed
    matches_data = UserService.format_matches_for_dashboard(
        db, sorted_matches_docs, user_id
    )

    # Get group rankings
    group_rankings = UserService.get_group_rankings(db, user_id)

    streak_display = (
        f"{stats['current_streak']}{stats['streak_type']}"
        if stats["processed_matches"]
        else "N/A"
    )

    return jsonify(
        {
            "user": user_data,
            "friends": friends_data,
            "requests": requests_data,
            "matches": matches_data,
            "group_rankings": group_rankings,
            "stats": {
                "total_matches": stats["total_games"],
                "win_percentage": stats["win_rate"],
                "current_streak": streak_display,
            },
        }
    )


# TODO: Add type hints for Agent clarity
@bp.route("/api/create_invite", methods=["POST"])
@login_required
def create_invite():
    """Generate a unique invite token and stores it in Firestore."""
    db = firestore.client()
    user_id = g.user["uid"]
    token = secrets.token_urlsafe(16)
    invite_ref = db.collection("invites").document(token)
    invite_ref.set(
        {
            "userId": user_id,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "used": False,
        }
    )
    return jsonify({"token": token})
