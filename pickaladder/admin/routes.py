from flask import (
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
)
from faker import Faker
import random
from datetime import datetime
from werkzeug.security import generate_password_hash
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text, or_

from pickaladder import db
from . import bp
from pickaladder.models import User, Friend, Match, Setting
from pickaladder.auth.utils import send_password_reset_email
from pickaladder.constants import USER_ID, USER_IS_ADMIN


@bp.before_request
def before_request():
    if not session.get(USER_IS_ADMIN):
        flash("You are not authorized to view this page.", "danger")
        return redirect(url_for("auth.login"))


@bp.route("/")
def admin():
    email_verification_setting = Setting.query.get("enforce_email_verification")
    return render_template(
        "admin.html", email_verification_setting=email_verification_setting
    )


@bp.route("/toggle_email_verification", methods=["POST"])
def toggle_email_verification():
    try:
        setting = Setting.query.get("enforce_email_verification")
        if setting:
            # Flip the boolean value represented as a string
            setting.value = "false" if setting.value == "true" else "true"
            db.session.commit()
            new_status = "enabled" if setting.value == "true" else "disabled"
            flash(f"Email verification requirement has been {new_status}.", "success")
        else:
            flash("Setting not found.", "danger")
    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred: {e}", "danger")
    return redirect(url_for(".admin"))


@bp.route("/matches")
def admin_matches():
    search_term = request.args.get("search", "")
    query = (
        db.session.query(Match)
        .join(User, Match.player1)
        .join(User, Match.player2, aliased=True)
    )

    if search_term:
        like_term = f"%{search_term}%"
        query = query.filter(
            or_(User.username.ilike(like_term), User.username.ilike(like_term))
        )

    matches = query.order_by(Match.match_date.desc()).all()

    return render_template(
        "admin_matches.html", matches=matches, search_term=search_term
    )


@bp.route("/delete_match/<string:match_id>")
def admin_delete_match(match_id):
    try:
        match = Match.query.get(match_id)
        if match:
            db.session.delete(match)
            db.session.commit()
            flash("Match deleted successfully.", "success")
        else:
            flash("Match not found.", "danger")
    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred: {e}", "danger")
    return redirect(url_for(".admin_matches"))


@bp.route("/friend_graph_data")
def friend_graph_data():
    users = User.query.all()
    friends = Friend.query.filter_by(status="accepted").all()

    nodes = [{"id": str(user.id), "label": user.username} for user in users]
    edges = [
        {"from": str(friend.user_id), "to": str(friend.friend_id)} for friend in friends
    ]

    return jsonify({"nodes": nodes, "edges": edges})


@bp.route("/reset_db", methods=["POST"])
def reset_db():
    try:
        # Using raw SQL for TRUNCATE, as it's more efficient than deleting all objects.
        db.session.execute(
            text("TRUNCATE TABLE friends, users, matches RESTART IDENTITY CASCADE")
        )
        db.session.commit()
        flash("Database has been reset.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred while resetting the database: {e}", "danger")
    return redirect(url_for(".admin"))


@bp.route("/reset-admin", methods=["POST"])
def reset_admin():
    try:
        User.query.update({User.is_admin: False})
        first_user = User.query.order_by(User.id).first()
        if first_user:
            first_user.is_admin = True
        db.session.commit()
        flash("Admin privileges have been reset.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred: {e}", "danger")
    return redirect(url_for(".admin"))


@bp.route("/delete_user/<uuid:user_id>")
def delete_user(user_id):
    try:
        user = User.query.get(user_id)
        if user:
            db.session.delete(user)
            db.session.commit()
            flash("User deleted successfully.", "success")
        else:
            flash("User not found.", "danger")
    except IntegrityError:
        db.session.rollback()
        flash("Cannot delete user as they are part of existing matches.", "danger")
    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred: {e}", "danger")
    return redirect(url_for("user.users"))


@bp.route("/promote_user/<uuid:user_id>")
def promote_user(user_id):
    try:
        user = User.query.get(user_id)
        if user:
            user.is_admin = True
            db.session.commit()
            flash(f"{user.username} has been promoted to admin.", "success")
        else:
            flash("User not found.", "danger")
    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred: {e}", "danger")
    return redirect(url_for("user.users"))


@bp.route("/reset_password/<uuid:user_id>")
def admin_reset_password(user_id):
    try:
        user = User.query.get(user_id)
        if user and user.email:
            send_password_reset_email(user)
            flash(f"Password reset link sent to {user.email}.", "success")
        elif user:
            flash("This user does not have an email address on file.", "warning")
        else:
            flash("User not found.", "danger")
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")
    return redirect(url_for("user.users"))


@bp.route("/verify_user/<uuid:user_id>", methods=["POST"])
def verify_user(user_id):
    try:
        user = User.query.get(user_id)
        if user:
            user.email_verified = True
            db.session.commit()
            flash(f"User {user.username} has been manually verified.", "success")
        else:
            flash("User not found.", "danger")
    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred: {e}", "danger")
    return redirect(url_for("user.users"))


@bp.route("/generate_users", methods=["POST"])
def generate_users():
    fake = Faker()
    new_users = []

    try:
        existing_usernames = set(
            u.username for u in User.query.with_entities(User.username).all()
        )

        for _ in range(10):
            name = fake.name()
            username = name.lower().replace(" ", "")
            if username in existing_usernames:
                username = f"{username}{random.randint(1, 999)}"  # nosec B311

            hashed_password = generate_password_hash("password", method="pbkdf2:sha256")
            new_user = User(
                username=username,
                password=hashed_password,
                email=f"{username}@example.com",
                name=name,
                dupr_rating=round(
                    fake.pyfloat(
                        left_digits=1,
                        right_digits=2,
                        positive=True,
                        min_value=1.0,
                        max_value=5.0,
                    ),
                    2,
                ),
            )
            db.session.add(new_user)
            new_users.append(new_user)

        # Flush to get IDs for relationships before creating friendships
        db.session.flush()

        # Create friendships between new users
        for i in range(len(new_users)):
            for j in range(i + 1, len(new_users)):
                if random.random() < 0.5:  # nosec B311
                    # Create accepted friendship both ways
                    friendship1 = Friend(
                        user_id=new_users[i].id,
                        friend_id=new_users[j].id,
                        status="accepted",
                    )
                    friendship2 = Friend(
                        user_id=new_users[j].id,
                        friend_id=new_users[i].id,
                        status="accepted",
                    )
                    db.session.add(friendship1)
                    db.session.add(friendship2)

        # Send friend requests to admin
        admin_id = session.get(USER_ID)
        if admin_id:
            num_requests = random.randint(0, len(new_users))  # nosec B311
            users_to_send_request = random.sample(new_users, num_requests)  # nosec B311
            for user in users_to_send_request:
                # Check if a friendship/request already exists
                existing = Friend.query.filter_by(
                    user_id=user.id, friend_id=admin_id
                ).first()
                if not existing:
                    friend_request = Friend(
                        user_id=user.id, friend_id=admin_id, status="pending"
                    )
                    db.session.add(friend_request)

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred while generating users: {e}", "danger")

    return render_template("generated_users.html", users=new_users)


@bp.route("/generate_matches", methods=["POST"])
def generate_matches():
    try:
        friends = Friend.query.filter_by(status="accepted").all()
        if not friends:
            flash("No friendships found to generate matches.", "warning")
            return redirect(url_for(".admin"))

        for _ in range(10):
            friendship = random.choice(friends)  # nosec B311
            player1_id, player2_id = friendship.user_id, friendship.friend_id

            score1 = random.randint(0, 11)  # nosec B311
            score2 = score1 - 2 if score1 >= 10 else random.randint(0, 11)  # nosec B311
            if abs(score1 - score2) < 2 and max(score1, score2) >= 11:
                score2 = random.randint(0, 11)  # nosec B311

            p1_score, p2_score = (
                (score1, score2)
                if random.random() < 0.5  # nosec B311
                else (score2, score1)
            )

            new_match = Match(
                player1_id=player1_id,
                player2_id=player2_id,
                player1_score=p1_score,
                player2_score=p2_score,
                match_date=datetime.utcnow(),
            )
            db.session.add(new_match)

        db.session.commit()
        flash("10 random matches generated successfully.", "success")

    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred while generating matches: {e}", "danger")

    return redirect(url_for(".admin"))
