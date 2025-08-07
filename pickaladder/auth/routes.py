import secrets
import re
from datetime import datetime, timedelta
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
import psycopg2

from pickaladder.db import get_db_connection
from . import bp
from pickaladder import mail
from .utils import generate_profile_picture
from pickaladder.errors import ValidationError, DuplicateResourceError
from pickaladder.constants import (
    USERS_TABLE,
    USER_ID,
    USER_USERNAME,
    USER_PASSWORD,
    USER_EMAIL,
    USER_NAME,
    USER_DUPR_RATING,
    USER_IS_ADMIN,
    USER_PROFILE_PICTURE,
    USER_PROFILE_PICTURE_THUMBNAIL,
    USER_EMAIL_VERIFIED,
    USER_RESET_TOKEN,
    USER_RESET_TOKEN_EXPIRATION,
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
            raise ValidationError("Password must contain at least one uppercase letter.")
        if not re.search(r"[a-z]", password):
            raise ValidationError("Password must contain at least one lowercase letter.")
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

        hashed_password = generate_password_hash(password, method="pbkdf2:sha256")
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            f"SELECT {USER_ID} FROM {USERS_TABLE} WHERE {USER_USERNAME} = %s", (username,)
        )
        if cur.fetchone():
            raise DuplicateResourceError("Username already exists. Please choose a different one.")

        try:
            cur.execute(
                f"INSERT INTO {USERS_TABLE} ({USER_USERNAME}, {USER_PASSWORD}, "
                f"{USER_EMAIL}, {USER_NAME}, {USER_DUPR_RATING}, {USER_IS_ADMIN}) "
                f"VALUES (%s, %s, %s, %s, %s, %s) RETURNING {USER_ID}",
                (username, hashed_password, email, name, dupr_rating, False),
            )
            user_id = cur.fetchone()[0]

            profile_picture_data, thumbnail_data = generate_profile_picture(name)
            cur.execute(
                f"UPDATE {USERS_TABLE} SET {USER_PROFILE_PICTURE} = %s, "
                f"{USER_PROFILE_PICTURE_THUMBNAIL} = %s "
                f"WHERE {USER_ID} = %s",
                (profile_picture_data, thumbnail_data, user_id),
            )

            msg = Message(
                "Verify your email",
                sender=current_app.config["MAIL_USERNAME"],
                recipients=[email],
            )
            msg.body = "Click the link to verify your email: {}".format(
                url_for("auth.verify_email", email=email, _external=True)
            )
            mail.send(msg)

            conn.commit()

            session[USER_ID] = str(user_id)
            session[USER_IS_ADMIN] = False
            current_app.logger.info(f"New user registered: {username}")

        except psycopg2.IntegrityError:
            conn.rollback()
            raise DuplicateResourceError("Username or email already exists.")
        except Exception:
            conn.rollback()
            # Let the centralized handler deal with this
            raise

        return redirect(url_for("user.dashboard"))
    return render_template("register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT {USER_ID} FROM {USERS_TABLE} WHERE {USER_IS_ADMIN} = TRUE")
    admin_exists = cur.fetchone()
    if not admin_exists:
        return redirect(url_for("auth.install"))

    if request.method == "POST":
        username = request.form[USER_USERNAME]
        password = request.form[USER_PASSWORD]
        cur.execute(
            f"SELECT * FROM {USERS_TABLE} WHERE {USER_USERNAME} = %s", (username,)
        )
        user = cur.fetchone()
        if not user or not check_password_hash(user[2], password):
            raise ValidationError("Invalid username or password.")

        session[USER_ID] = str(user[0])
        session[USER_IS_ADMIN] = user[6]
        return redirect(url_for("user.dashboard"))
    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@bp.route("/install", methods=["GET", "POST"])
def install():
    conn = get_db_connection()
    cur = conn.cursor()

    # Check if an admin user already exists on GET request.
    if request.method == "GET":
        cur.execute(f"SELECT {USER_ID} FROM {USERS_TABLE} WHERE {USER_IS_ADMIN} = TRUE")
        if cur.fetchone():
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
        try:
            sql = (
                f"INSERT INTO {USERS_TABLE} ({USER_USERNAME}, {USER_PASSWORD}, "
                f"{USER_EMAIL}, {USER_NAME}, {USER_DUPR_RATING}, {USER_IS_ADMIN}) "
                f"VALUES (%s, %s, %s, %s, %s, %s) RETURNING {USER_ID}"
            )
            cur.execute(sql, (username, hashed_password, email, name, dupr_rating, True))
            user_id = cur.fetchone()[0]

            profile_picture_data, thumbnail_data = generate_profile_picture(name)
            cur.execute(
                f"UPDATE {USERS_TABLE} SET {USER_PROFILE_PICTURE} = %s, "
                f"{USER_PROFILE_PICTURE_THUMBNAIL} = %s "
                f"WHERE {USER_ID} = %s",
                (profile_picture_data, thumbnail_data, user_id),
            )
            conn.commit()

            session[USER_ID] = str(user_id)
            session[USER_IS_ADMIN] = True
            current_app.logger.info(f"Admin user created: {username}")
        except psycopg2.IntegrityError:
            conn.rollback()
            raise DuplicateResourceError("Username or email already exists.")
        except Exception:
            conn.rollback()
            raise

        return redirect(url_for("user.dashboard"))
    return render_template("install.html")


from .utils import send_password_reset_email

@bp.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form[USER_EMAIL]
        send_password_reset_email(email)
        # Show a generic message to prevent user enumeration
        flash("If an account with that email exists, a password reset link has been sent.", "info")
        return redirect(url_for("auth.login"))

    return render_template("forgot_password.html")


@bp.route("/reset/<token>", methods=["GET", "POST"])
def reset_password_with_token(token):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Find user by token
    cur.execute(f"SELECT {USER_ID}, {USER_RESET_TOKEN} FROM {USERS_TABLE} WHERE {USER_RESET_TOKEN_EXPIRATION} > %s", (datetime.utcnow(),))
    users_with_tokens = cur.fetchall()

    user_id = None
    for user in users_with_tokens:
        if check_password_hash(user[USER_RESET_TOKEN], token):
            user_id = user[USER_ID]
            break

    if not user_id:
        # Using flash still makes sense here as it's a redirect
        flash("Password reset link is invalid or has expired.", "danger")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        password = request.form[USER_PASSWORD]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            raise ValidationError("Passwords do not match.")

        # Add password complexity validation here as well
        if len(password) < 8:
            raise ValidationError("Password must be at least 8 characters long.")

        hashed_password = generate_password_hash(password)
        cur.execute(
            f"UPDATE {USERS_TABLE} SET {USER_PASSWORD} = %s, {USER_RESET_TOKEN} = NULL, {USER_RESET_TOKEN_EXPIRATION} = NULL WHERE {USER_ID} = %s",
            (hashed_password, user_id),
        )
        conn.commit()
        flash("Your password has been updated!", "success")
        return redirect(url_for("auth.login"))

    return render_template("reset_password_with_token.html", token=token)


@bp.route("/change_password", methods=["GET", "POST"])
def change_password():
    if USER_ID not in session:
        return redirect(url_for("auth.login"))
    user_id = session[USER_ID]

    if request.method == "POST":
        password = request.form[USER_PASSWORD]
        confirm_password = request.form["confirm_password"]

        if not password or password != confirm_password:
            raise ValidationError("Passwords do not match.")

        hashed_password = generate_password_hash(password, method="pbkdf2:sha256")
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            f"UPDATE {USERS_TABLE} SET {USER_PASSWORD} = %s WHERE {USER_ID} = %s",
            (hashed_password, user_id),
        )
        conn.commit()
        flash("Password changed successfully.", "success")
        return redirect(url_for("user.dashboard"))

    # For GET request
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {USERS_TABLE} WHERE {USER_ID} = %s", (user_id,))
    user = cur.fetchone()
    return render_template("change_password.html", user=user)


@bp.route(f"/verify_email/<{USER_EMAIL}>")
def verify_email(email):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        f"UPDATE {USERS_TABLE} SET {USER_EMAIL_VERIFIED} = TRUE WHERE {USER_EMAIL} = %s",
        (email,),
    )
    conn.commit()
    flash("Email verified. You can now log in.", "success")
    return redirect(url_for("auth.login"))
