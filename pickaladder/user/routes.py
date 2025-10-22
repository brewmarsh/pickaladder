import uuid
import os
from flask import (
    render_template,
    request,
    redirect,
    url_for,
    flash,
    current_app,
    jsonify,
    g,
)
from firebase_admin import firestore, storage
from werkzeug.utils import secure_filename

from . import bp
from .forms import UpdateProfileForm
from pickaladder.auth.decorators import login_required
from pickaladder.group.utils import get_group_leaderboard


@bp.route("/dashboard")
@login_required
def dashboard():
    """
    Renders the user dashboard. Most data is loaded asynchronously via API endpoints.
    The profile update form is passed to the template.
    """
    current_app.logger.info("Dashboard page loaded")
    user_data = g.user
    form = UpdateProfileForm(data=user_data)
    return render_template("user_dashboard.html", form=form, user=user_data)


@bp.route("/<string:user_id>")
@login_required
def view_user(user_id):
    """Displays a user's public profile."""
    db = firestore.client()
    profile_user_ref = db.collection("users").document(user_id)
    profile_user = profile_user_ref.get()

    if not profile_user.exists:
        flash("User not found.", "danger")
        return redirect(url_for(".users"))

    profile_user_data = profile_user.to_dict()
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
        .where("status", "==", "accepted")
        .limit(10)
        .stream()
    )
    friends = [db.collection("users").document(f.id).get() for f in friends_query]

    # Fetch user's match history (limited for display)
    matches_as_p1 = (
        db.collection("matches").where("player1Ref", "==", profile_user_ref).stream()
    )
    matches_as_p2 = (
        db.collection("matches").where("player2Ref", "==", profile_user_ref).stream()
    )
    matches = list(matches_as_p1) + list(matches_as_p2)
    # This is a simplified representation. A real implementation would need
    # to fetch opponent data for each match.

    return render_template(
        "user_profile.html",
        profile_user=profile_user_data,
        friends=friends,
        matches=matches,
        is_friend=is_friend,
        friend_request_sent=friend_request_sent,
    )


@bp.route("/users")
@login_required
def users():
    """Lists and allows searching for users."""
    db = firestore.client()
    search_term = request.args.get("search", "")
    query = db.collection("users")

    if search_term:
        # Firestore doesn't support case-insensitive search natively.
        # This searches for an exact username match.
        query = query.where("username", ">=", search_term).where(
            "username", "<=", search_term + "\uf8ff"
        )

    all_users = [doc for doc in query.limit(20).stream() if doc.id != g.user["uid"]]

    return render_template("users.html", users=all_users, search_term=search_term)


@bp.route("/send_friend_request/<string:friend_id>", methods=["POST"])
@login_required
def send_friend_request(friend_id):
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
    """Displays the user's friends and pending requests."""
    db = firestore.client()
    current_user_id = g.user["uid"]
    friends_ref = db.collection("users").document(current_user_id).collection("friends")

    # Fetch accepted friends
    accepted_docs = friends_ref.where("status", "==", "accepted").stream()
    accepted_ids = [doc.id for doc in accepted_docs]
    accepted_friends = (
        [db.collection("users").document(uid).get() for uid in accepted_ids]
        if accepted_ids
        else []
    )

    # Fetch pending requests (where the other user was the initiator)
    requests_docs = (
        friends_ref.where("status", "==", "pending")
        .where("initiator", "==", False)
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


@bp.route("/update_profile", methods=["POST"])
@login_required
def update_profile():
    db = firestore.client()
    bucket = storage.bucket(os.environ.get("FIREBASE_STORAGE_BUCKET"))
    user_id = g.user["uid"]
    user_ref = db.collection("users").document(user_id)
    form = UpdateProfileForm()

    if form.validate_on_submit():
        try:
            update_data = {
                "darkMode": bool(form.dark_mode.data),
            }
            if form.dupr_rating.data is not None:
                update_data["duprRating"] = float(form.dupr_rating.data)

            profile_picture_file = form.profile_picture.data
            if profile_picture_file:
                secure_filename(profile_picture_file.filename or "profile.jpg")
                content_type = profile_picture_file.content_type

                # Path in Firebase Storage
                path = f"profile-pictures/{user_id}/original_{uuid.uuid4().hex}.jpg"
                blob = bucket.blob(path)

                # Upload the file
                blob.upload_from_file(profile_picture_file, content_type=content_type)

                # Make the file public and get the URL
                blob.make_public()
                update_data["profilePictureUrl"] = blob.public_url

                # Note: The thumbnail URL will be set by a Cloud Function.
                # The function should be triggered by the upload and update the
                # 'profilePictureThumbnailUrl' field in the user's document.

            user_ref.update(update_data)
            flash("Profile updated successfully.", "success")
        except Exception as e:
            current_app.logger.error(f"Error updating profile: {e}")
            flash(f"An error occurred: {e}", "danger")
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in {getattr(form, field).label.text}: {error}", "danger")

    return redirect(url_for(".dashboard"))


@bp.route("/api/dashboard")
@login_required
def api_dashboard():
    """Provides dashboard data as JSON, including matches and group rankings."""
    db = firestore.client()
    user_id = g.user["uid"]
    user_ref = db.collection("users").document(user_id)
    user_data = user_ref.get().to_dict()

    # Fetch friends
    friends_query = (
        user_ref.collection("friends").where("status", "==", "accepted").stream()
    )
    friend_ids = [doc.id for doc in friends_query]
    friends_data = []
    if friend_ids:
        friend_docs = (
            db.collection("users").where("__name__", "in", friend_ids).stream()
        )
        friends_data = [{"id": doc.id, **doc.to_dict()} for doc in friend_docs]

    # Fetch pending friend requests
    requests_query = (
        user_ref.collection("friends")
        .where("status", "==", "pending")
        .where("initiator", "==", False)
        .stream()
    )
    request_ids = [doc.id for doc in requests_query]
    requests_data = []
    if request_ids:
        request_docs = (
            db.collection("users").where("__name__", "in", request_ids).stream()
        )
        requests_data = [{"id": doc.id, **doc.to_dict()} for doc in request_docs]

    # Fetch recent matches
    matches_as_p1 = (
        db.collection("matches").where("player1Ref", "==", user_ref).limit(5).stream()
    )
    matches_as_p2 = (
        db.collection("matches").where("player2Ref", "==", user_ref).limit(5).stream()
    )

    matches_data = []
    for match_doc in list(matches_as_p1) + list(matches_as_p2):
        match = match_doc.to_dict()
        opponent_ref = (
            match["player2Ref"]
            if match["player1Ref"].id == user_id
            else match["player1Ref"]
        )
        opponent = opponent_ref.get()
        if opponent.exists:
            opponent_data = opponent.to_dict()
            matches_data.append(
                {
                    "id": match_doc.id,
                    "opponent_username": opponent_data.get("username", "N/A"),
                    "opponent_id": opponent.id,
                    "user_score": match["player1Score"]
                    if match["player1Ref"].id == user_id
                    else match["player2Score"],
                    "opponent_score": match["player2Score"]
                    if match["player1Ref"].id == user_id
                    else match["player1Score"],
                    "date": match.get("matchDate", "N/A"),
                }
            )

    # Get group rankings
    group_rankings = []
    my_groups_query = (
        db.collection("groups").where("members", "array_contains", user_ref).stream()
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
