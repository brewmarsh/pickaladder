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
from pickaladder.group.utils import get_group_leaderboard
from pickaladder.utils import EmailError, send_email

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

    h2h_stats = None
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

        # H2H STATS
        my_wins = 0
        my_losses = 0
        point_diff = 0

        # Singles matches
        singles_query_1 = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("player1Id", "==", current_user_id))
            .where(filter=firestore.FieldFilter("player2Id", "==", user_id))
            .where(filter=firestore.FieldFilter("status", "==", "completed"))
            .stream()
        )
        singles_query_2 = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("player1Id", "==", user_id))
            .where(filter=firestore.FieldFilter("player2Id", "==", current_user_id))
            .where(filter=firestore.FieldFilter("status", "==", "completed"))
            .stream()
        )

        for match in singles_query_1:
            data = match.to_dict()
            if data.get("winnerId") == current_user_id:
                my_wins += 1
            else:
                my_losses += 1
            point_diff += data.get("player1Score", 0) - data.get("player2Score", 0)

        for match in singles_query_2:
            data = match.to_dict()
            if data.get("winnerId") == current_user_id:
                my_wins += 1
            else:
                my_losses += 1
            point_diff += data.get("player2Score", 0) - data.get("player1Score", 0)

        # Doubles matches - Firestore does not support multiple array_contains on
        # different fields.
        # Fetch all doubles matches for the current user and filter in Python.
        doubles_query = (
            db.collection("matches")
            .where(
                filter=firestore.FieldFilter(
                    "participants", "array_contains", current_user_id
                )
            )
            .where(filter=firestore.FieldFilter("matchType", "==", "doubles"))
            .where(filter=firestore.FieldFilter("status", "==", "completed"))
            .stream()
        )

        for match in doubles_query:
            data = match.to_dict()
            participants = data.get("participants", [])
            if user_id in participants:
                team1_ids = data.get("team1Id", [])
                team2_ids = data.get("team2Id", [])

                user_in_team1 = current_user_id in team1_ids
                opponent_in_team2 = user_id in team2_ids
                user_in_team2 = current_user_id in team2_ids
                opponent_in_team1 = user_id in team1_ids

                if user_in_team1 and opponent_in_team2:
                    if data.get("winnerId") == "team1":
                        my_wins += 1
                    else:
                        my_losses += 1
                    point_diff += (
                        data.get("player1Score", 0) - data.get("player2Score", 0)
                    )
                elif user_in_team2 and opponent_in_team1:
                    if data.get("winnerId") == "team2":
                        my_wins += 1
                    else:
                        my_losses += 1
                    point_diff += (
                        data.get("player2Score", 0) - data.get("player1Score", 0)
                    )

        if my_wins > 0 or my_losses > 0:
            h2h_stats = {
                "wins": my_wins,
                "losses": my_losses,
                "point_diff": point_diff,
            }

    # Fetch user's friends (limited for display)
    friends_query = (
        profile_user_ref.collection("friends")
        .where(filter=firestore.FieldFilter("status", "==", "accepted"))
        .limit(10)
        .stream()
    )
    friends = [db.collection("users").document(f.id).get() for f in friends_query]

    # Fetch user's match history
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
    matches_as_t1 = (
        db.collection("matches")
        .where(
            filter=firestore.FieldFilter("team1", "array_contains", profile_user_ref)
        )
        .stream()
    )
    matches_as_t2 = (
        db.collection("matches")
        .where(
            filter=firestore.FieldFilter("team2", "array_contains", profile_user_ref)
        )
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

    wins = 0
    losses = 0
    all_processed_matches = []

    for match_doc in unique_matches:
        match_data = match_doc.to_dict()
        match_type = match_data.get("matchType", "singles")
        p1_score = match_data.get("player1Score", 0)
        p2_score = match_data.get("player2Score", 0)

        user_won = False
        user_lost = False

        if match_type == "doubles":
            team1_refs = match_data.get("team1", [])
            in_team1 = any(ref.id == user_id for ref in team1_refs)

            if in_team1:
                if p1_score > p2_score:
                    user_won = True
                else:
                    user_lost = True
            else:  # in team 2
                if p2_score > p1_score:
                    user_won = True
                else:
                    user_lost = True
        else:
            is_player1 = match_data.get("player1Ref") == profile_user_ref
            if is_player1:
                if p1_score > p2_score:
                    user_won = True
                else:
                    user_lost = True
            else:  # is_player2
                if p2_score > p1_score:
                    user_won = True
                else:
                    user_lost = True

        if user_won:
            wins += 1
        elif user_lost:
            losses += 1

        all_processed_matches.append(
            {
                "doc": match_doc,
                "data": match_data,
                "date": match_data.get("matchDate") or match_doc.create_time,
                "user_won": user_won,
            }
        )

    record = {"wins": wins, "losses": losses}
    total_games = wins + losses
    win_rate = (wins / total_games) * 100 if total_games > 0 else 0

    # Sort and Limit for display
    all_processed_matches.sort(
        key=lambda x: x["date"] or datetime.datetime.min, reverse=True
    )

    current_streak = 0
    streak_type = "N/A"
    if all_processed_matches:
        last_result = all_processed_matches[0]["user_won"]
        streak_type = "W" if last_result else "L"
        for match in all_processed_matches:
            if match["user_won"] == last_result:
                current_streak += 1
            else:
                break

    display_items = all_processed_matches[:20]

    # Collect all user refs needed for batch fetching
    needed_refs = set()
    needed_refs.add(profile_user_ref)

    for item in display_items:
        data = item["data"]
        match_type = data.get("matchType", "singles")
        if match_type == "doubles":
            needed_refs.update(data.get("team1", []))
            needed_refs.update(data.get("team2", []))
        else:
            if data.get("player1Ref"):
                needed_refs.add(data.get("player1Ref"))
            if data.get("player2Ref"):
                needed_refs.add(data.get("player2Ref"))

    # Fetch all unique users in one batch
    unique_refs_list = list(needed_refs)
    users_map = {}
    if unique_refs_list:
        users_docs = db.get_all(unique_refs_list)
        users_map = {doc.id: doc.to_dict() for doc in users_docs if doc.exists}

    def get_username(ref, default="Unknown"):
        if not ref:
            return default
        u_data = users_map.get(ref.id)
        if u_data:
            return u_data.get("username", default)
        return default

    final_matches = []
    for item in display_items:
        data = item["data"]
        m_id = item["doc"].id
        match_type = data.get("matchType", "singles")

        # Construct object compatible with template
        match_obj = {
            "id": m_id,
            "match_date": data.get("matchDate"),
            "player1_score": data.get("player1Score", 0),
            "player2_score": data.get("player2Score", 0),
            "player1_id": "",
            "player1": {"username": "Unknown"},
            "player2": {"id": "", "username": "Unknown"},
        }

        if match_type == "doubles":
            team1_refs = data.get("team1", [])
            team2_refs = data.get("team2", [])
            in_team1 = any(ref.id == user_id for ref in team1_refs)

            if in_team1:
                # Profile user is in Team 1 (Player 1 slot)
                match_obj["player1_id"] = user_id
                match_obj["player1"] = {
                    "id": user_id,
                    "username": profile_user_data.get("username"),
                }

                # Opponent is Team 2 (Player 2 slot)
                opp_name = "Unknown Team"
                opp_id = ""
                if team2_refs:
                    opp_ref = team2_refs[0]
                    opp_id = opp_ref.id
                    opp_name = get_username(opp_ref)
                    if len(team2_refs) > 1 or len(team1_refs) > 1:
                        opp_name += " (Doubles)"

                match_obj["player2"] = {"id": opp_id, "username": opp_name}

            else:
                # Profile user is in Team 2 (Player 2 slot)
                match_obj["player1_id"] = ""  # Not profile user

                # Opponent is Team 1 (Player 1 slot)
                opp_name = "Unknown Team"
                opp_id = ""
                if team1_refs:
                    opp_ref = team1_refs[0]
                    opp_id = opp_ref.id
                    opp_name = get_username(opp_ref)
                    if len(team1_refs) > 1 or len(team2_refs) > 1:
                        opp_name += " (Doubles)"

                match_obj["player1"] = {"id": opp_id, "username": opp_name}
                match_obj["player2"] = {
                    "id": user_id,
                    "username": profile_user_data.get("username"),
                }

        else:
            # Singles
            p1_ref = data.get("player1Ref")
            p2_ref = data.get("player2Ref")

            if p1_ref and p1_ref.id == user_id:
                match_obj["player1_id"] = user_id
                match_obj["player1"] = {
                    "id": user_id,
                    "username": profile_user_data.get("username"),
                }

                opp_name = get_username(p2_ref)
                opp_id = p2_ref.id if p2_ref else ""
                match_obj["player2"] = {"id": opp_id, "username": opp_name}
            else:
                match_obj["player1_id"] = p1_ref.id if p1_ref else ""
                opp_name = get_username(p1_ref)
                opp_id = p1_ref.id if p1_ref else ""
                match_obj["player1"] = {"id": opp_id, "username": opp_name}

                match_obj["player2"] = {
                    "id": user_id,
                    "username": profile_user_data.get("username"),
                }

        final_matches.append(match_obj)

    return render_template(
        "user_profile.html",
        profile_user=profile_user_data,
        friends=friends,
        matches=final_matches,
        is_friend=is_friend,
        friend_request_sent=friend_request_sent,
        record=record,
        user=g.user,
        total_games=total_games,
        win_rate=win_rate,
        current_streak=current_streak,
        streak_type=streak_type,
        h2h_stats=h2h_stats,
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
        "friends.html",
        friends=accepted_friends,
        requests=pending_requests,
        sent_requests=sent_requests,
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


def _get_player_info(player_ref, users_map):
    """Return a dictionary with player info."""
    player_data = users_map.get(player_ref.id)
    if not player_data:
        return {"id": player_ref.id, "username": "Unknown", "thumbnail_url": ""}
    return {
        "id": player_ref.id,
        "username": player_data.get("username", "Unknown"),
        "thumbnail_url": player_data.get("thumbnail_url", ""),
    }


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
        refs = [db.collection("users").document(uid) for uid in friend_ids]
        friend_docs = db.get_all(refs)
        friends_data = [
            {"id": doc.id, **doc.to_dict()} for doc in friend_docs if doc.exists
        ]

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
        refs = [db.collection("users").document(uid) for uid in request_ids]
        request_docs = db.get_all(refs)
        requests_data = [
            {"id": doc.id, **doc.to_dict()} for doc in request_docs if doc.exists
        ]

    # Fetch recent matches (Singles and Doubles)
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
    unique_matches = {match.id: match for match in all_matches}.values()
    sorted_matches = sorted(
        unique_matches,
        key=lambda x: x.to_dict().get("matchDate") or x.create_time,
        reverse=True,
    )[:10]

    # Batch fetch user data for all players in the matches
    player_refs = set()
    for match_doc in sorted_matches:
        match = match_doc.to_dict()
        if match.get("player1Ref"):
            player_refs.add(match["player1Ref"])
        if match.get("player2Ref"):
            player_refs.add(match["player2Ref"])
        for ref in match.get("team1", []):
            player_refs.add(ref)
        for ref in match.get("team2", []):
            player_refs.add(ref)

    users_map = {}
    if player_refs:
        user_docs = db.get_all(list(player_refs))
        users_map = {doc.id: doc.to_dict() for doc in user_docs if doc.exists}

    matches_data = []
    for match_doc in sorted_matches:
        match = match_doc.to_dict()
        p1_score = match.get("player1Score", 0)
        p2_score = match.get("player2Score", 0)
        winner = "player1" if p1_score > p2_score else "player2"

        if match.get("matchType") == "doubles":
            team1 = [_get_player_info(ref, users_map) for ref in match.get("team1", [])]
            team2 = [_get_player_info(ref, users_map) for ref in match.get("team2", [])]
            player1_info = team1
            player2_info = team2
        else:
            player1_info = _get_player_info(match["player1Ref"], users_map)
            player2_info = _get_player_info(match["player2Ref"], users_map)

        matches_data.append(
            {
                "id": match_doc.id,
                "player1": player1_info,
                "player2": player2_info,
                "player1_score": p1_score,
                "player2_score": p2_score,
                "winner": winner,
                "date": match.get("matchDate", "N/A"),
                "is_group_match": bool(match.get("groupId")),
                "match_type": match.get("matchType", "singles"),
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
