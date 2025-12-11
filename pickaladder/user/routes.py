"""Routes for the user blueprint."""

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
from pickaladder.group.utils import get_group_leaderboard
from pickaladder.utils import send_email

from . import bp
from .forms import UpdateProfileForm, UpdateUserForm


class MockPagination:
    """A mock pagination object."""

    def __init__(self, items):
        """Initialize the mock pagination object."""
        self.items = items
        self.pages = 1


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
                    "Your email has been updated. Please check your new email address to verify it.",
                    "info",
                )
            except auth.EmailAlreadyExistsError:
                flash("That email address is already in use.", "danger")
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


@bp.route("/<string:user_id>")
@login_required
def view_user(user_id):
    """Display a user's public profile."""
    db = firestore.client()
    profile_user_ref = db.collection("users").document(user_id)
    profile_user = profile_user_ref.get()

    if not profile_user.exists:
        flash("User not found.", "danger")
        return redirect(url_for(".users"))

    profile_user_data = profile_user.to_dict()
    profile_user_data["id"] = user_id
    current_user_id = g.user["uid"]

    # Fetch friendship status
    friend_request_sent = False
    is_friend = False

    if current_user_id != user_id:
        friend_ref = (
            db.collection("users")
            .document(current_user_id)
            .collection("friends")
            .document(user_id)
        )
        friend_doc = friend_ref.get()
        if friend_doc.exists:
            status = friend_doc.to_dict().get("status")
            if status == "accepted":
                is_friend = True
            elif status == "pending":
                friend_request_sent = True

    # Fetch user's friends (limited for display)
    friends_query = (
        profile_user_ref.collection("friends")
        .where(filter=firestore.FieldFilter("status", "==", "accepted"))
        .limit(10)
        .stream()
    )
    friends = [db.collection("users").document(f.id).get() for f in friends_query]

    # Fetch user's match history (limited for display)
    matches_as_p1 = (
        db.collection("matches")
        .where(filter=firestore.FieldFilter("player1Ref", "==", profile_user_ref))
        .stream()
    )
    matches_as_p2 = (
        db.collection("matches")
        .where(filter=firestore.FieldFilter("player2Ref", "==", profile_user_ref))
        .stream()
    )
    matches = list(matches_as_p1) + list(matches_as_p2)

    # Calculate win/loss record
    wins = 0
    losses = 0
    for match_doc in matches:
        match_data = match_doc.to_dict()
        is_player1 = match_data.get("player1Ref") == profile_user_ref

        player1_score = match_data.get("player1Score", 0)
        player2_score = match_data.get("player2Score", 0)

        if is_player1:
            if player1_score > player2_score:
                wins += 1
            else:
                losses += 1
        else:  # is_player2
            if player2_score > player1_score:
                wins += 1
            else:
                losses += 1
    record = {"wins": wins, "losses": losses}

    return render_template(
        "user_profile.html",
        profile_user=profile_user_data,
        friends=friends,
        matches=matches,
        is_friend=is_friend,
        friend_request_sent=friend_request_sent,
        record=record,
        user=g.user,
    )


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
    except Exception as e:
        current_app.logger.error(f"Error sending friend request: {e}")
        flash("An error occurred while sending the friend request.", "danger")

    return redirect(url_for(".users"))


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
    accepted_friends = (
        [db.collection("users").document(uid).get() for uid in accepted_ids]
        if accepted_ids
        else []
    )

    # Fetch pending requests (where the other user was the initiator)
    requests_docs = (
        friends_ref.where(filter=firestore.FieldFilter("status", "==", "pending"))
        .where(filter=firestore.FieldFilter("initiator", "==", False))
        .stream()
    )
    request_ids = [doc.id for doc in requests_docs]
    pending_requests = (
        [db.collection("users").document(uid).get() for uid in request_ids]
        if request_ids
        else []
    )

    return render_template(
        "friends.html", friends=accepted_friends, requests=pending_requests
    )


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


@bp.route("/api/dashboard")
@login_required
def api_dashboard():
    """Provide dashboard data as JSON, including matches and group rankings."""
    db = firestore.client()
    user_id = g.user["uid"]
    user_ref = db.collection("users").document(user_id)
    user_data = user_ref.get().to_dict()

    # Fetch friends
    friends_query = (
        user_ref.collection("friends")
        .where(filter=firestore.FieldFilter("status", "==", "accepted"))
        .stream()
    )
    friend_ids = [doc.id for doc in friends_query]
    friends_data = []
    if friend_ids:
        friend_docs = (
            db.collection("users")
            .where(filter=firestore.FieldFilter("__name__", "in", friend_ids))
            .stream()
        )
        friends_data = [{"id": doc.id, **doc.to_dict()} for doc in friend_docs]

    # Fetch pending friend requests
    requests_query = (
        user_ref.collection("friends")
        .where(filter=firestore.FieldFilter("status", "==", "pending"))
        .where(filter=firestore.FieldFilter("initiator", "==", False))
        .stream()
    )
    request_ids = [doc.id for doc in requests_query]
    requests_data = []
    if request_ids:
        request_docs = (
            db.collection("users")
            .where(filter=firestore.FieldFilter("__name__", "in", request_ids))
            .stream()
        )
        requests_data = [{"id": doc.id, **doc.to_dict()} for doc in request_docs]

    # Fetch recent matches (Singles and Doubles)
    # Note: We fetch all matches and sort in-memory to correctly identify the most recent ones
    # without requiring a composite index for (playerXRef, matchDate).
    matches_as_p1 = (
        db.collection("matches")
        .where(filter=firestore.FieldFilter("player1Ref", "==", user_ref))
        .stream()
    )
    matches_as_p2 = (
        db.collection("matches")
        .where(filter=firestore.FieldFilter("player2Ref", "==", user_ref))
        .stream()
    )
    matches_as_t1 = (
        db.collection("matches")
        .where(filter=firestore.FieldFilter("team1", "array_contains", user_ref))
        .stream()
    )
    matches_as_t2 = (
        db.collection("matches")
        .where(filter=firestore.FieldFilter("team2", "array_contains", user_ref))
        .stream()
    )

    all_matches = (
        list(matches_as_p1)
        + list(matches_as_p2)
        + list(matches_as_t1)
        + list(matches_as_t2)
    )
    # Deduplicate matches by ID
    unique_matches = {match.id: match for match in all_matches}.values()
    # Sort by date (assuming matchDate exists)
    sorted_matches = sorted(
        unique_matches,
        key=lambda x: x.to_dict().get("matchDate") or x.create_time,
        reverse=True,
    )[:5]

    matches_data = []
    for match_doc in sorted_matches:
        match = match_doc.to_dict()
        match_type = match.get("matchType", "singles")

        opponent_name = "N/A"
        opponent_id = None
        user_score = 0
        opponent_score = 0

        if match_type == "doubles":
            # Check if user is in team 1
            team1_refs = match.get("team1", [])
            in_team1 = any(ref.id == user_id for ref in team1_refs)

            if in_team1:
                user_score = match.get("player1Score", 0)
                opponent_score = match.get("player2Score", 0)
                # Pick first opponent from team 2
                team2_refs = match.get("team2", [])
                if team2_refs:
                    opp_ref = team2_refs[0]
                    opponent_id = opp_ref.id
                    opp_doc = opp_ref.get()
                    if opp_doc.exists:
                        opponent_name = opp_doc.to_dict().get("username", "Unknown")
                    else:
                        opponent_name = "Unknown"
                else:
                    opponent_name = "Unknown Team"
            else:
                # Must be in team 2
                user_score = match.get("player2Score", 0)
                opponent_score = match.get("player1Score", 0)
                # Pick first opponent from team 1
                if team1_refs:
                    opp_ref = team1_refs[0]
                    opponent_id = opp_ref.id
                    opp_doc = opp_ref.get()
                    if opp_doc.exists:
                        opponent_name = opp_doc.to_dict().get("username", "Unknown")
                    else:
                        opponent_name = "Unknown"
                else:
                    opponent_name = "Unknown Team"

            if len(team1_refs) > 1 or len(match.get("team2", [])) > 1:
                opponent_name += " (Doubles)"

        else:
            # Singles logic
            if match["player1Ref"].id == user_id:
                user_score = match["player1Score"]
                opponent_score = match["player2Score"]
                opponent_ref = match["player2Ref"]
            else:
                user_score = match["player2Score"]
                opponent_score = match["player1Score"]
                opponent_ref = match["player1Ref"]

            opponent_id = opponent_ref.id
            opponent = opponent_ref.get()
            if opponent.exists:
                opponent_name = opponent.to_dict().get("username", "N/A")

        matches_data.append(
            {
                "id": match_doc.id,
                "opponent_username": opponent_name,
                "opponent_id": opponent_id,
                "user_score": user_score,
                "opponent_score": opponent_score,
                "date": match.get("matchDate", "N/A"),
                "is_group_match": bool(match.get("groupId")),
            }
        )

    # Get group rankings
    group_rankings = []
    my_groups_query = (
        db.collection("groups")
        .where(filter=firestore.FieldFilter("members", "array_contains", user_ref))
        .stream()
    )
    for group_doc in my_groups_query:
        group_data = group_doc.to_dict()
        leaderboard = get_group_leaderboard(group_doc.id)
        rank = "N/A"
        for i, player in enumerate(leaderboard):
            if player["id"] == user_id:
                rank = i + 1
                break
        group_rankings.append(
            {
                "group_id": group_doc.id,
                "group_name": group_data.get("name", "N/A"),
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
