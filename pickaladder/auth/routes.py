import re
from flask import (
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    current_app,
)
from flask_mail import Message
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
import uuid

from pickaladder import db
from . import bp
from pickaladder import mail
from .utils import generate_profile_picture, send_password_reset_email
from pickaladder.errors import ValidationError, DuplicateResourceError
from pickaladder.models import User
from pickaladder.constants import (
    USER_ID,
    USER_USERNAME,
    USER_PASSWORD,
    USER_EMAIL,
    USER_NAME,
    USER_DUPR_RATING,
    USER_IS_ADMIN,
)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form[USER_USERNAME]
        password = request.form[USER_PASSWORD]
        confirm_password = request.form["confirm_password"]
        email = request.form[USER_EMAIL]
        name = request.form[USER_NAME]

        # --- Validation Logic ---
        if len(username) < 3 or len(username) > 25:
            raise ValidationError("Username must be between 3 and 25 characters.")
        if not username.isalnum():
            raise ValidationError("Username must contain only letters and numbers.")
        if password != confirm_password:
            raise ValidationError("Passwords do not match.")
        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters long.")
        if not re.search(r"[A-Z]", password):
            raise ValidationError(
                "Password must contain at least one uppercase letter."
            )
        if not re.search(r"[a-z]", password):
            raise ValidationError(
                "Password must contain at least one lowercase letter."
            )
        if not re.search(r"\d", password):
            raise ValidationError("Password must contain at least one number.")
        # --- End Validation Logic ---

        try:
            dupr_rating = (
                float(request.form[USER_DUPR_RATING])
                if request.form[USER_DUPR_RATING]
                else None
            )
        except ValueError:
            raise ValidationError("Invalid DUPR rating.")

        if User.query.filter_by(username=username).first() is not None:
            raise DuplicateResourceError(
                "Username already exists. Please choose a different one."
            )
        if User.query.filter_by(email=email).first() is not None:
            raise DuplicateResourceError("Email address is already registered.")

        hashed_password = generate_password_hash(password, method="pbkdf2:sha256")
        profile_picture_data, thumbnail_data = generate_profile_picture(name)

        new_user = User(
            username=username,
            password=hashed_password,
            email=email,
            name=name,
            dupr_rating=dupr_rating,
            profile_picture=profile_picture_data,
            profile_picture_thumbnail=thumbnail_data,
        )

        try:
            db.session.add(new_user)
            db.session.commit()

            msg = Message(
                "Verify your email",
                sender=current_app.config["MAIL_USERNAME"],
                recipients=[email],
            )
            verify_url = url_for("auth.verify_email", email=email, _external=True)
            msg.body = f"Click the link to verify your email: {verify_url}"
            mail.send(msg)

            session[USER_ID] = str(new_user.id)
            session[USER_IS_ADMIN] = new_user.is_admin
            current_app.logger.info(f"New user registered: {username}")

        except IntegrityError:
            db.session.rollback()
            raise DuplicateResourceError("Username or email already exists.")
        except Exception:
            db.session.rollback()
            raise

        return redirect(url_for("user.dashboard"))
    return render_template("register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if User.query.filter_by(is_admin=True).first() is None:
        return redirect(url_for("auth.install"))

    if request.method == "POST":
        username = request.form[USER_USERNAME]
        password = request.form[USER_PASSWORD]

        user = User.query.filter_by(username=username).first()

        if user is None or not check_password_hash(user.password, password):
            raise ValidationError("Invalid username or password.")

        session[USER_ID] = str(user.id)
        session[USER_IS_ADMIN] = user.is_admin
        return redirect(url_for("user.dashboard"))
    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@bp.route("/install", methods=["GET", "POST"])
def install():
    if User.query.filter_by(is_admin=True).first() is not None:
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        username = request.form[USER_USERNAME]
        password = request.form[USER_PASSWORD]
        email = request.form[USER_EMAIL]
        name = request.form[USER_NAME]
        try:
            dupr_rating = (
                float(request.form[USER_DUPR_RATING])
                if request.form[USER_DUPR_RATING]
                else None
            )
        except ValueError:
            raise ValidationError("Invalid DUPR rating.")

        hashed_password = generate_password_hash(password, method="pbkdf2:sha256")
        profile_picture_data, thumbnail_data = generate_profile_picture(name)

        admin_user = User(
            username=username,
            password=hashed_password,
            email=email,
            name=name,
            dupr_rating=dupr_rating,
            is_admin=True,
            profile_picture=profile_picture_data,
            profile_picture_thumbnail=thumbnail_data,
        )

        try:
            db.session.add(admin_user)
            db.session.commit()

            session[USER_ID] = str(admin_user.id)
            session[USER_IS_ADMIN] = admin_user.is_admin
            current_app.logger.info(f"Admin user created: {username}")
        except IntegrityError:
            db.session.rollback()
            raise DuplicateResourceError("Username or email already exists.")
        except Exception:
            db.session.rollback()
            raise

        return redirect(url_for("user.dashboard"))
    return render_template("install.html")


@bp.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form[USER_EMAIL]
        user = User.query.filter_by(email=email).first()
        if user:
            send_password_reset_email(user)
        message = (
            "If an account with that email exists, a password reset link has been sent."
        )
        flash(message, "info")
        return redirect(url_for("auth.login"))

    return render_template("forgot_password.html")


@bp.route("/reset/<token>", methods=["GET", "POST"])
def reset_password_with_token(token):
    user = User.verify_reset_token(token)
    if not user:
        flash("Password reset link is invalid or has expired.", "danger")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        password = request.form[USER_PASSWORD]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            raise ValidationError("Passwords do not match.")
        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters long.")

        user.password = generate_password_hash(password)
        user.reset_token = None
        user.reset_token_expiration = None
        db.session.commit()

        flash("Your password has been updated!", "success")
        return redirect(url_for("auth.login"))

    return render_template("reset_password_with_token.html", token=token)


@bp.route("/change_password", methods=["GET", "POST"])
def change_password():
    if USER_ID not in session:
        return redirect(url_for("auth.login"))

    user = db.session.get(User, uuid.UUID(session[USER_ID]))
    if not user:
        session.clear()
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        password = request.form[USER_PASSWORD]
        confirm_password = request.form["confirm_password"]

        if not password or password != confirm_password:
            raise ValidationError("Passwords do not match.")

        user.password = generate_password_hash(password, method="pbkdf2:sha256")
        db.session.commit()

        flash("Password changed successfully.", "success")
        return redirect(url_for("user.dashboard"))

    return render_template("change_password.html", user=user)


@bp.route(f"/verify_email/<{USER_EMAIL}>")
def verify_email(email):
    user = User.query.filter_by(email=email).first()
    if user:
        user.email_verified = True
        db.session.commit()
        flash("Email verified. You can now log in.", "success")
    else:
        flash("Invalid verification link.", "danger")
    return redirect(url_for("auth.login"))
