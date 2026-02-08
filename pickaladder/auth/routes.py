"""Routes for authentication."""

import re
from typing import Any, Union

from firebase_admin import auth, firestore
from flask import (
    Response,
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import login_user, logout_user
from werkzeug.exceptions import UnprocessableEntity

from pickaladder.errors import DuplicateResourceError
from pickaladder.user.helpers import wrap_user
from pickaladder.user.services import UserService
from pickaladder.utils import EmailError, send_email

from . import bp
from .forms import ChangePasswordForm, LoginForm, RegisterForm


# TODO: Add type hints for Agent clarity
@bp.route("/register", methods=["GET", "POST"])
def register() -> Union[Response, str]:
    """Register a new user."""
    invite_token = request.args.get("invite_token")
    if invite_token:
        session["invite_token"] = invite_token
    form = RegisterForm()
    if form.validate_on_submit():
        db = firestore.client()
        username = form.username.data
        email = form.email.data
        password = form.password.data

        # Check if username is already taken in Firestore
        users_ref = db.collection("users")
        if (
            users_ref.where(filter=firestore.FieldFilter("username", "==", username))
            .limit(1)
            .get()
        ):
            flash("Username already exists. Please choose a different one.", "danger")
            return redirect(url_for(".register"))

        try:
            # Create user in Firebase Authentication
            user_record = auth.create_user(
                email=email, password=password, email_verified=False
            )

            # Send email verification
            verification_link = auth.generate_email_verification_link(email)
            send_email(
                to=email,
                subject="Verify Your Email",
                template="email/verify_email.html",
                user={"username": username},
                verification_link=verification_link,
            )

            # Create user document in Firestore
            user_doc_ref = db.collection("users").document(user_record.uid)
            user_doc_ref.set(
                {
                    "username": username,
                    "email": email,
                    "name": form.name.data,
                    "duprRating": float(form.dupr_rating.data),
                    "isAdmin": False,
                    "createdAt": firestore.SERVER_TIMESTAMP,
                }
            )

            # Check for ghost user merge
            if UserService.merge_ghost_user(db, user_doc_ref, email):
                # Check for tournament invites to show welcome toast
                invites = UserService.get_pending_tournament_invites(
                    db, user_doc_ref.id
                )
                if invites:
                    session["show_welcome_invites"] = len(invites)

            # Handle invite token
            invite_token = session.pop("invite_token", None)
            if invite_token:
                invite_ref = db.collection("invites").document(invite_token)
                invite = invite_ref.get()
                if invite.exists and not invite.to_dict().get("used"):
                    inviter_id = invite.to_dict()["userId"]
                    # Create friendship
                    batch = db.batch()
                    batch.set(
                        db.collection("users")
                        .document(user_record.uid)
                        .collection("friends")
                        .document(inviter_id),
                        {"status": "accepted"},
                    )
                    batch.set(
                        db.collection("users")
                        .document(inviter_id)
                        .collection("friends")
                        .document(user_record.uid),
                        {"status": "accepted"},
                    )
                    batch.commit()
                    invite_ref.update({"used": True})

            flash(
                "Registration successful! Please check your email to verify your "
                "account.",
                "success",
            )
            # Client-side will handle login and redirect to dashboard
            return redirect(url_for(".login", next=request.args.get("next")))

        except auth.EmailAlreadyExistsError:
            flash("Email address is already registered.", "danger")
        except EmailError as e:
            current_app.logger.error(f"Email error during registration: {e}")
            flash(str(e), "danger")
        except Exception as e:
            current_app.logger.error(f"Error during registration: {e}")
            flash("An unexpected error occurred during registration.", "danger")

        return redirect(url_for(".register"))

    return render_template("register.html", form=form)


# TODO: Add type hints for Agent clarity
@bp.route("/login", methods=["GET", "POST"])
def login() -> Union[Response, str]:
    """Render the login page.

    The actual login process is handled by the Firebase client-side SDK.
    The client will get an ID token and send it with subsequent requests.
    """
    current_app.logger.info("Login page loaded")
    db = firestore.client()
    # Check if an admin user exists to determine if we should run install
    admin_query = (
        db.collection("users")
        .where(filter=firestore.FieldFilter("isAdmin", "==", True))
        .limit(1)
        .get()
    )
    if not admin_query:
        return redirect(url_for("auth.install"))

    form = LoginForm()
    # The form is now just for presentation, validation is on the client
    return render_template("login.html", form=form)


# TODO: Add type hints for Agent clarity
def _generate_unique_username(db: Any, base_username: str) -> str:
    """Generate a unique username by appending a number if the base username exists."""
    username = base_username
    i = 1
    while (
        db.collection("users")
        .where(filter=firestore.FieldFilter("username", "==", username))
        .limit(1)
        .get()
    ):
        username = f"{base_username}{i}"
        i += 1
    return username


# TODO: Add type hints for Agent clarity
@bp.route("/session_login", methods=["POST"])
def session_login() -> Response:
    """Handle session login.

    This endpoint is called from the client-side after a successful Firebase login.
    It receives the ID token, verifies it, and creates a server-side session.
    """
    id_token = request.json.get("idToken")
    try:
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token["uid"]
        db = firestore.client()
        user_doc_ref = db.collection("users").document(uid)
        user_doc = user_doc_ref.get()

        if user_doc.exists:
            user_info = user_doc.to_dict()
        else:
            # User doesn't exist, so create a new profile
            user_record = auth.get_user(uid)
            email = user_record.email
            name = user_record.display_name or email.split("@")[0]
            base_username = re.sub(r"[^a-zA-Z0-9_.]", "", name.lower())
            username = _generate_unique_username(db, base_username)

            user_info = {
                "username": username,
                "email": email,
                "name": name,
                "duprRating": None,
                "isAdmin": False,
                "createdAt": firestore.SERVER_TIMESTAMP,
            }
            user_doc_ref.set(user_info)

            # Check for ghost user merge
            if UserService.merge_ghost_user(db, user_doc_ref, email):
                # Check for tournament invites to show welcome toast
                invites = UserService.get_pending_tournament_invites(db, uid)
                if invites:
                    session["show_welcome_invites"] = len(invites)

        remember = request.json.get("remember", False)
        user = wrap_user(user_info, uid=uid)
        login_user(user, remember=remember)

        session["user_id"] = uid
        session["is_admin"] = user_info.get("isAdmin", False)
        return jsonify({"status": "success"})

    except Exception as e:
        current_app.logger.error(f"Error during session login: {e}")
        return jsonify(
            {"status": "error", "message": "Invalid token or server error."}
        ), 401


# TODO: Add type hints for Agent clarity
@bp.route("/logout")
def logout() -> Response:
    """Log the user out.

    The actual logout is handled by the Firebase client-side SDK.
    This route is for clearing any server-side session info if needed.
    """
    session.clear()
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))


# TODO: Add type hints for Agent clarity
@bp.route("/install", methods=["GET", "POST"])
def install() -> Union[Response, str]:
    """Install the application by creating an admin user."""
    db = firestore.client()
    # Check if an admin user already exists
    admin_query = (
        db.collection("users")
        .where(filter=firestore.FieldFilter("isAdmin", "==", True))
        .limit(1)
        .get()
    )
    if admin_query:
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        username = request.form.get("username")

        if not all([email, password, username]):
            flash("Missing required fields for admin creation.", "danger")
            return redirect(url_for(".install"))

        try:
            # Create user in Firebase Auth
            admin_user_record = auth.create_user(
                email=email, password=password, email_verified=True
            )

            # Create admin user document in Firestore
            admin_doc_ref = db.collection("users").document(admin_user_record.uid)
            admin_doc_ref.set(
                {
                    "username": username,
                    "email": email,
                    "name": request.form.get("name", ""),
                    "duprRating": float(request.form.get("dupr_rating") or 0),
                    "isAdmin": True,
                    "createdAt": firestore.SERVER_TIMESTAMP,
                }
            )

            # Also create the email verification setting
            settings_ref = db.collection("settings").document(
                "enforceEmailVerification"
            )
            settings_ref.set({"value": True})

            flash("Admin user created successfully. You can now log in.", "success")
            return redirect(url_for("auth.login"))

        except auth.EmailAlreadyExistsError:
            # This could happen in a race condition. We'll try to find the
            # user and grant them admin rights if they are not already an admin.
            try:
                user = auth.get_user_by_email(email)
                user_doc_ref = db.collection("users").document(user.uid)
                user_doc = user_doc_ref.get()
                if user_doc.exists and not user_doc.to_dict().get("isAdmin"):
                    user_doc_ref.update({"isAdmin": True})
                    flash("An existing user was promoted to admin.", "info")
                    return redirect(url_for("auth.login"))
                else:
                    raise DuplicateResourceError(
                        "An admin user with this email already exists."
                    )
            except auth.UserNotFoundError:
                raise UnprocessableEntity("Could not create or find user.")

        except Exception as e:
            current_app.logger.error(f"Error during installation: {e}")
            flash("An unexpected error occurred during installation.", "danger")

    return render_template("install.html")


# TODO: Add type hints for Agent clarity
@bp.route("/change_password", methods=["GET", "POST"])
def change_password() -> Union[Response, str]:
    """Render the change password page.

    The actual password change is handled by the Firebase client-side SDK.
    """
    if not g.get("user"):
        return redirect(url_for("auth.login"))

    form = ChangePasswordForm()
    if form.validate_on_submit():
        # The form is for display and validation, but the actual password
        # change is handled by the Firebase client-side SDK.
        # We can flash a message to inform the user.
        flash("Your password has been updated.", "success")
        return redirect(url_for("user.profile"))

    return render_template("change_password.html", user=g.user, form=form)
