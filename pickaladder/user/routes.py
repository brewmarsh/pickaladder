"""Routes for the user blueprint."""

from __future__ import annotations

import os
import secrets
import tempfile
from typing import TYPE_CHECKING, Any

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

if TYPE_CHECKING:
    pass


class MockPagination:
    """A mock pagination object."""

    # TODO: Add type hints for Agent clarity
    def __init__(self, items: list[Any]) -> None:
        """Initialize the mock pagination object."""
        self.items = items
        self.pages = 1


@bp.route("/community")
@login_required
def view_community() -> str | Any:
    """Display the community hub with friends, requests, and user discovery."""
    db = firestore.client()
    current_user_id = g.user["uid"]
    search_term = request.args.get("search", "").strip()

    # 1. Fetch Friends
    friends = UserService.get_user_friends(db, current_user_id)

    # 2. Fetch Pending Requests (Received)
    pending_requests = UserService.get_user_pending_requests(db, current_user_id)

    # 3. Fetch Sent Requests (Outgoing)
    sent_requests = UserService.get_user_sent_requests(db, current_user_id)

    # 4. Discover Users
    discover_users_all = UserService.get_all_users(
        db, current_user_id, limit=50
    )

    friend_ids = {f["id"] for f in friends}
    sent_request_ids = {s["id"] for s in sent_requests}
    received_request_ids = {r["id"] for r in pending_requests}

    # Filter by search term if present
    if search_term:
        term = search_term.lower()
        def matches_search(u):
            return (
                term in u.get("username", "").lower() 
                or term in u.get("name", "").lower()
            )
        
        friends = [f for f in friends if matches_search(f)]
        pending_requests = [r for r in pending_requests if matches_search(r)]
        sent_requests = [s for s in sent_requests if matches_search(s)]
        discover_users_all = [u for u in discover_users_all if matches_search(u)]

    discover_users = []
    for user_data in discover_users_all:
        # Tag status for template action buttons
        if user_data["id"] in friend_ids:
            user_data["status"] = "friend"
        elif user_data["id"] in sent_request_ids:
            user_data["status"] = "sent"
        elif user_data["id"] in received_request_ids:
            user_data["status"] = "received"
        else:
            user_data["status"] = "stranger"
        discover_users.append(user_data)

    return render_template(
        "user/community.html",
        friends=friends,
        pending_requests=pending_requests,
        sent_requests=sent_requests,
        discover_users=discover_users,
        search_term=search_term,
    )


@bp.route("/edit_profile", methods=["GET", "POST"])
@login_required
def edit_profile() -> str | Any:
    """Handle user profile updates for name, username, and email."""
    db = firestore.client()
    user_id = g.user["uid"]
    user_ref = db.collection("users").document(user_id)
    user_data = g.user
    form = UpdateUserForm(data=user_data)

    if form.validate_on_submit():
        new_email = form.email.data
        new_username = form.username.data
        update_data: dict[str, Any] = {
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


@bp.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard() -> str | Any:
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
        if user_data.get("dark_mode") is not None:
            form.dark_mode.data = bool(user_data.get("dark_mode"))

    if form.validate_on_submit():
        try:
            update_data: dict[str, Any] = {
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


@bp.route("/<string:user_id>")
@login_required
def view_user(user_id: str) -> str | Any:
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


@bp.route("/users")
@login_required
def users() -> str | Any:
    """List and allows searching for users (Legacy/Discovery)."""
    db = firestore.client()
    current_user_id = g.user["uid"]
    search_term = request.args.get("search", "")
    query = db.collection("users")

    if search_term:
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
        user_data["id"] = user_doc.id

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

    pagination = MockPagination(user_items)
    fof: list[Any] = []

    return render_template(
        "users.html", pagination=pagination, search_term=search_term, fof=fof
    )


@bp.route("/send_friend_request/<string:friend_id>", methods=["POST"])
@login_required
def send_friend_request(friend_id: str) -> Any:
    """Send a friend request to another user."""
    db = firestore.client()
    current_user_id = g.user["uid"]
    if current_user_id == friend_id:
        flash("You cannot send a friend request to yourself.", "danger")
        return redirect(url_for(".users"))

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


@bp.route("/friends")
@login_required
def friends() -> str | Any:
    """Display the user's friends and pending requests."""
    db = firestore.client()
    current_user_id = g.user["uid"]
    
    friends = UserService.get_user_friends(db, current_user_id)
    pending_requests = UserService.get_user_pending_requests(db, current_user_id)
    sent_requests = UserService.get_user_sent_requests(db, current_user_id)

    return render_template(
        "friends/index.html",
        friends=friends,
        requests=pending_requests,
        sent_requests=sent_requests,
    )


@bp.route("/accept_friend_request/<string:friend_id>", methods=["POST"])
@login_required
def accept_friend_request(friend_id: str) -> Any:
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


@bp.route("/decline_friend_request/<string:friend_id>", methods=["POST"])
@login_required
def decline_friend_request(friend_id: str) -> Any:
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


@bp.route("/api/dashboard")
@login_required
def api_dashboard() -> Any:
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


@bp.route("/api/create_invite", methods=["POST"])
@login_required
def create_invite() -> Any:
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