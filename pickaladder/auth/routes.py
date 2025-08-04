from flask import (
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    Response,
    current_app,
)
from flask_mail import Message
from werkzeug.security import generate_password_hash, check_password_hash
import os
import random
import string
from io import BytesIO

from pickaladder.db import get_db_connection
from . import bp
from pickaladder import mail
from .utils import generate_profile_picture
import psycopg2
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
)


@bp.route("/register", methods=["GET", "POST"])
def register():
    error = None
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
            return "Invalid DUPR rating."
        hashed_password = generate_password_hash(password, method="pbkdf2:sha256")
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            f"SELECT * FROM {USERS_TABLE} WHERE {USER_USERNAME} = %s", (username,)
        )
        existing_user = cur.fetchone()
        if existing_user:
            error = "Username already exists. Please choose a different one."
            return render_template("register.html", error=error)
        try:
            cur.execute(
                f"INSERT INTO {USERS_TABLE} ({USER_USERNAME}, {USER_PASSWORD}, "
                f"{USER_EMAIL}, {USER_NAME}, {USER_DUPR_RATING}, {USER_IS_ADMIN}) "
                f"VALUES (%s, %s, %s, %s, %s, %s) RETURNING {USER_ID}",
                (username, hashed_password, email, name, dupr_rating, False),
            )
            user_id = cur.fetchone()[0]
            conn.commit()
            session[USER_ID] = str(user_id)
            session[USER_IS_ADMIN] = False
            current_app.logger.info(f"New user registered: {username}")

            profile_picture_data, thumbnail_data = generate_profile_picture(name)
            cur.execute(
                f"UPDATE {USERS_TABLE} SET {USER_PROFILE_PICTURE} = %s, "
                f"{USER_PROFILE_PICTURE_THUMBNAIL} = %s "
                f"WHERE {USER_ID} = %s",
                (profile_picture_data, thumbnail_data, user_id),
            )
            conn.commit()
            msg = Message(
                "Verify your email",
                sender=current_app.config["MAIL_USERNAME"],
                recipients=[email],
            )
            msg.body = "Click the link to verify your email: {}".format(
                url_for("auth.verify_email", email=email, _external=True)
            )
            mail.send(msg)
        except psycopg2.IntegrityError:
            conn.rollback()
            flash("Username or email already exists.", "danger")
            return redirect(url_for("auth.register"))
        except Exception as e:
            conn.rollback()
            flash(f"An error occurred: {e}", "danger")
            return "An error occurred during registration."
        return redirect(url_for("user.dashboard"))
    return render_template("register.html", error=error)


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
        if user and check_password_hash(user[2], password):
            session[USER_ID] = str(user[0])
            session[USER_IS_ADMIN] = user[6]
            return redirect(url_for("user.dashboard"))
        else:
            return render_template("login.html", error="Invalid username or password.")
    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@bp.route("/install", methods=["GET", "POST"])
def install():
    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == "GET":
        # Check if an admin user already exists.
        cur.execute(f"SELECT {USER_ID} FROM {USERS_TABLE} WHERE {USER_IS_ADMIN} = TRUE")
        admin_exists = cur.fetchone()
        if admin_exists:
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
            return "Invalid DUPR rating."
        hashed_password = generate_password_hash(password, method="pbkdf2:sha256")
        try:
            sql = (
                f"INSERT INTO {USERS_TABLE} ({USER_USERNAME}, {USER_PASSWORD}, "
                f"{USER_EMAIL}, {USER_NAME}, {USER_DUPR_RATING}, {USER_IS_ADMIN}) "
                f"VALUES (%s, %s, %s, %s, %s, %s) RETURNING {USER_ID}"
            )
            cur.execute(
                sql,
                (username, hashed_password, email, name, dupr_rating, True),
            )
            user_id = cur.fetchone()[0]
            conn.commit()
            session[USER_ID] = str(user_id)
            session[USER_IS_ADMIN] = True
            current_app.logger.info(f"New user registered: {username}")

            profile_picture_data, thumbnail_data = generate_profile_picture(name)
            cur.execute(
                f"UPDATE {USERS_TABLE} SET {USER_PROFILE_PICTURE} = %s, "
                f"{USER_PROFILE_PICTURE_THUMBNAIL} = %s "
                f"WHERE {USER_ID} = %s",
                (profile_picture_data, thumbnail_data, user_id),
            )
            conn.commit()
        except psycopg2.IntegrityError:
            conn.rollback()
            flash("Username or email already exists.", "danger")
            return redirect(url_for("auth.install"))
        except Exception as e:
            conn.rollback()
            current_app.logger.error(f"An error occurred during installation: {e}")
            flash(f"An error occurred: {e}", "danger")
            return "An error occurred during installation."
        return redirect(url_for("user.dashboard"))
    return render_template("install.html")


@bp.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form[USER_EMAIL]
        msg = Message(
            "Password reset",
            sender=current_app.config["MAIL_USERNAME"],
            recipients=[email],
        )
        msg.body = "Click the link to reset your password: {}".format(
            url_for("auth.reset_password", email=email, _external=True)
        )
        mail.send(msg)
        return "Password reset email sent."
    return render_template("forgot_password.html")


@bp.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    email = request.args.get(USER_EMAIL)
    if request.method == "POST":
        password = request.form[USER_PASSWORD]
        hashed_password = generate_password_hash(password, method="pbkdf2:sha256")
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            f"UPDATE {USERS_TABLE} SET {USER_PASSWORD} = %s WHERE {USER_EMAIL} = %s",
            (hashed_password, email),
        )
        conn.commit()
        return redirect(url_for("auth.login"))
    return render_template("reset_password.html", email=email)


@bp.route("/change_password", methods=["GET", "POST"])
def change_password():
    if USER_ID not in session:
        return redirect(url_for("auth.login"))
    user_id = session[USER_ID]
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {USERS_TABLE} WHERE {USER_ID} = %s", (user_id,))
    user = cur.fetchone()
    if request.method == "POST":
        password = request.form[USER_PASSWORD]
        confirm_password = request.form["confirm_password"]
        if password and password == confirm_password:
            hashed_password = generate_password_hash(password, method="pbkdf2:sha256")
            cur.execute(
                f"UPDATE {USERS_TABLE} SET {USER_PASSWORD} = %s WHERE {USER_ID} = %s",
                (hashed_password, user_id),
            )
            conn.commit()
            return redirect(url_for("user.dashboard"))
        else:
            return render_template(
                "change_password.html", user=user, error="Passwords do not match."
            )
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
