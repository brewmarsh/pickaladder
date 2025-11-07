"""Admin routes for the application."""

import random

from faker import Faker
from firebase_admin import auth, firestore
from flask import (
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    url_for,
)

from pickaladder.auth.decorators import login_required

from . import bp


@bp.route("/")
@login_required(admin_required=True)
def admin():
    """Render the main admin dashboard."""
    # Authorization check is now here, after g.user is guaranteed to be loaded.
    if not g.user or not g.user.get("isAdmin"):
        flash("You are not authorized to view this page.", "danger")
        return redirect(url_for("auth.login"))

    db = firestore.client()
    setting_ref = db.collection("settings").document("enforceEmailVerification")
    email_verification_setting = setting_ref.get()
    return render_template(
        "admin.html",
        email_verification_setting=email_verification_setting.to_dict()
        if email_verification_setting.exists
        else {"value": False},
    )


@bp.route("/toggle_email_verification", methods=["POST"])
def toggle_email_verification():
    """Toggle the global setting for requiring email verification."""
    db = firestore.client()
    setting_ref = db.collection("settings").document("enforceEmailVerification")
    try:
        setting = setting_ref.get()
        current_value = (
            setting.to_dict().get("value", False) if setting.exists else False
        )
        new_value = not current_value
        setting_ref.set({"value": new_value})
        new_status = "enabled" if new_value else "disabled"
        flash(f"Email verification requirement has been {new_status}.", "success")
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")
    return redirect(url_for(".admin"))


@bp.route("/matches")
def admin_matches():
    """Display a list of all matches."""
    db = firestore.client()
    matches_query = (
        db.collection("matches")
        .order_by("createdAt", direction=firestore.Query.DESCENDING)
        .limit(50)
    )
    matches = matches_query.stream()
    # This is a simplified view. A full view would need to resolve player refs.
    return render_template("admin_matches.html", matches=matches)


@bp.route("/delete_match/<string:match_id>", methods=["POST"])
def admin_delete_match(match_id):
    """Delete a match document from Firestore."""
    db = firestore.client()
    try:
        db.collection("matches").document(match_id).delete()
        flash("Match deleted successfully.", "success")
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")
    return redirect(url_for(".admin_matches"))


@bp.route("/friend_graph_data")
def friend_graph_data():
    """Provide data for a network graph of users and their friendships."""
    db = firestore.client()
    users = db.collection("users").stream()
    nodes = []
    edges = []
    for user in users:
        user_data = user.to_dict()
        nodes.append({"id": user.id, "label": user_data.get("username", user.id)})
        # Fetch friends for this user
        friends_query = (
            db.collection("users")
            .document(user.id)
            .collection("friends")
            .where(filter=firestore.FieldFilter("status", "==", "accepted"))
            .stream()
        )
        for friend in friends_query:
            # Add edge only once
            if user.id < friend.id:
                edges.append({"from": user.id, "to": friend.id})
    return jsonify({"nodes": nodes, "edges": edges})


@bp.route("/delete_user/<string:user_id>", methods=["POST"])
def delete_user(user_id):
    """Delete a user from Firebase Auth and Firestore."""
    db = firestore.client()
    try:
        # Delete from Firebase Auth
        auth.delete_user(user_id)
        # Delete from Firestore
        db.collection("users").document(user_id).delete()
        # Note: This doesn't clean up references in matches/groups, which would
        # require a more complex cleanup process (e.g., a Cloud Function).
        flash("User deleted successfully.", "success")
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")
    return redirect(url_for("user.users"))


@bp.route("/promote_user/<string:user_id>", methods=["POST"])
def promote_user(user_id):
    """Promote a user to admin status."""
    db = firestore.client()
    try:
        user_ref = db.collection("users").document(user_id)
        user_ref.update({"isAdmin": True})
        username = user_ref.get().to_dict().get("username", "user")
        flash(f"{username} has been promoted to admin.", "success")
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")
    return redirect(url_for("user.users"))


@bp.route("/generate_users", methods=["POST"])
def generate_users():
    """Generate a number of fake users for testing."""
    db = firestore.client()
    fake = Faker()
    users_to_create = 10
    new_users = []
    try:
        for _ in range(users_to_create):
            username = fake.user_name()
            email = fake.email()
            password = fake.password(
                length=12,
                special_chars=True,
                digits=True,
                upper_case=True,
                lower_case=True,
            )

            # Create user in Auth
            user_record = auth.create_user(email=email, password=password)

            # Create user in Firestore
            user_doc = {
                "username": username,
                "email": email,
                "name": fake.name(),
                "duprRating": round(random.uniform(2.5, 7.0), 2),  # nosec
                "isAdmin": False,
                "createdAt": firestore.SERVER_TIMESTAMP,
            }
            db.collection("users").document(user_record.uid).set(user_doc)
            new_users.append({"uid": user_record.uid, **user_doc})

        flash(f"{len(new_users)} users generated successfully.", "success")
    except Exception as e:
        flash(f"An error occurred while generating users: {e}", "danger")

    return render_template("generated_users.html", users=new_users)


@bp.route("/generate_matches", methods=["POST"])
def generate_matches():
    """Generate random matches between existing users."""
    db = firestore.client()
    fake = Faker()
    try:
        users = list(db.collection("users").limit(20).stream())
        if len(users) < 2:
            flash("Not enough users to generate matches.", "warning")
            return redirect(url_for(".admin"))

        matches_to_create = 10
        for _ in range(matches_to_create):
            p1, p2 = random.sample(users, 2)  # nosec
            db.collection("matches").add(
                {
                    "player1Ref": p1.reference,
                    "player2Ref": p2.reference,
                    "player1Score": random.randint(5, 11),  # nosec
                    "player2Score": random.randint(5, 11),  # nosec
                    "matchDate": fake.date_between(start_date="-1y", end_date="today"),
                    "createdAt": firestore.SERVER_TIMESTAMP,
                }
            )
        flash(f"{matches_to_create} random matches generated.", "success")
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")

    return redirect(url_for(".admin_matches"))
