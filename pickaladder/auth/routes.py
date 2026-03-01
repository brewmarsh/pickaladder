"""Routes for authentication."""

import re
from typing import Any, cast

from firebase_admin import auth, firestore
from flask import (
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

from pickaladder.constants.messages import AUTH_MESSAGES
from pickaladder.errors import DuplicateResourceError
from pickaladder.user import UserService
from pickaladder.user.helpers import wrap_user
from pickaladder.utils import EmailError, send_email

from . import bp
from .forms import ChangePasswordForm, LoginForm, RegisterForm
from .services import AuthService


def _verify_bearer_token(auth_header: str) -> str | None:
    """Verify Firebase ID token from Bearer header."""
    if not auth_header.startswith("Bearer "):
        return None

    id_token = auth_header[7:].strip()
    try:
        decoded_token = auth.verify_id_token(id_token)
        uid = cast(str, decoded_token["uid"])
        # Sync session for subsequent requests
        session["user_id"] = uid
        session.permanent = True
        return uid
    except Exception as e:
        current_app.logger.debug(f"Token verification failed: {e}")
        return None


def _get_uid_from_request() -> str | None:
    """Extract UID from session or Authorization header."""
    if uid := session.get("user_id"):
        return cast(str, uid)

    if auth_header := request.headers.get("Authorization"):
        return _verify_bearer_token(auth_header)

    return None


def _handle_impersonation(uid: str) -> tuple[str, bool]:
    """Check for impersonation and return the target ID and status."""
    impersonate_id = session.get("impersonate_id")
    is_admin = session.get("is_admin", False)
    if impersonate_id and is_admin:
        return cast(str, impersonate_id), True
    return uid, False


def _initialize_test_user(id_to_load: str) -> None:
    """Provide a dummy user for testing environments."""
    is_admin = session.get("is_admin", False)
    g.user = wrap_user(
        {"username": "testuser", "isAdmin": is_admin, "uid": id_to_load},
        uid=id_to_load,
    )


def _cleanup_missing_user_session(is_impersonating: bool) -> None:
    """Clear session or impersonation data when user is not found."""
    if not is_impersonating:
        session.clear()
        return

    session.pop("impersonate_id", None)
    g.is_impersonating = False


def _fetch_user_doc(id_to_load: str) -> Any:
    """Fetch user document from Firestore."""
    db = firestore.client()
    return db.collection("users").document(id_to_load).get()


def _populate_g_user(user_doc: Any, id_to_load: str, is_impersonating: bool) -> None:
    """Populate g.user and sync session admin status."""
    g.user = wrap_user(user_doc.to_dict(), uid=id_to_load)
    if not is_impersonating:
        session["is_admin"] = g.user.get("isAdmin", False)


def _handle_missing_user(id_to_load: str, is_impersonating: bool) -> None:
    """Handle the case where a user document is missing."""
    if current_app.config.get("TESTING"):
        _initialize_test_user(id_to_load)
        return
    _cleanup_missing_user_session(is_impersonating)


def _load_user_document(id_to_load: str, is_impersonating: bool) -> None:
    """Fetch user from Firestore and populate g.user."""
    try:
        user_doc = _fetch_user_doc(id_to_load)
        _process_user_doc(user_doc, id_to_load, is_impersonating)
    except Exception as e:
        _handle_load_user_error(id_to_load, is_impersonating, e)


def _process_user_doc(user_doc: Any, id_to_load: str, is_impersonating: bool) -> None:
    """Process the fetched user document."""
    if not user_doc.exists:
        _handle_missing_user(id_to_load, is_impersonating)
        return
    _populate_g_user(user_doc, id_to_load, is_impersonating)


def _handle_load_user_error(
    id_to_load: str, is_impersonating: bool, e: Exception
) -> None:
    """Handle errors during user document loading."""
    current_app.logger.error(f"Error loading user {id_to_load}: {e}")
    if not is_impersonating:
        session.clear()


@bp.before_app_request
def load_user_from_auth_source() -> None:
    """Reliably populate g.user from session or Authorization header."""
    g.user = None
    g.is_impersonating = False

    uid = _get_uid_from_request()
    if not uid:
        return

    id_to_load, is_impersonating = _handle_impersonation(uid)
    g.is_impersonating = is_impersonating
    _load_user_document(id_to_load, is_impersonating)


@bp.route("/check_username")
def check_username() -> Any:
    """Check if a username is available (Ajax)."""
    username = request.args.get("username", "").strip()
    if not username:
        return jsonify({"available": False, "message": "Username is required."})

    db = firestore.client()
    is_taken = AuthService.is_username_taken(db, username)
    return jsonify({"available": not is_taken})


@bp.route("/register", methods=["GET", "POST"])
def register() -> Any:
    """Register a new user."""
    db = firestore.client()
    invite_token = request.args.get("invite_token") or session.get("invite_token")
    invite_name = None

    if invite_token:
        session["invite_token"] = invite_token
        invite_name = AuthService.get_invite_name(db, invite_token)

    form = RegisterForm()
    if not form.validate_on_submit():
        return render_template(
            "register.html",
            form=form,
            invite_name=invite_name,
            invite_token=invite_token,
        )

    username = cast(str, form.username.data)
    email = cast(str, form.email.data)

    if db and AuthService.is_username_taken(db, username):
        flash(AUTH_MESSAGES["USERNAME_EXISTS"], "danger")
        return redirect(url_for(".register"))

    return AuthService.execute_registration(form, username, email)


# TODO: Add type hints for Agent clarity
@bp.route("/login", methods=["GET", "POST"])
def login() -> Any:
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


def _finalize_session_login(
    user_info: dict[str, Any], uid: str, remember: bool
) -> None:
    """Initialize Flask-Login and server-side session."""
    user = wrap_user(user_info, uid=uid)
    login_user(user, remember=remember)
    session["user_id"] = uid
    session["is_admin"] = user_info.get("isAdmin", False)
    if remember:
        session.permanent = True


@bp.route("/session_login", methods=["POST"])
def session_login() -> Any:
    """Handle session login after Firebase client-side authentication."""
    id_token = request.json.get("idToken")
    registration_data = request.json.get("registrationData")
    try:
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token["uid"]
        db = firestore.client()

        user_info = AuthService.get_or_create_user_profile(db, uid, registration_data)
        remember = request.json.get("remember", False)
        _finalize_session_login(user_info, uid, remember)

        return jsonify({"status": "success"})

    except Exception as e:
        current_app.logger.error(f"Error during session login: {e}")
        return jsonify(
            {"status": "error", "message": "Invalid token or server error."}
        ), 401


# TODO: Add type hints for Agent clarity
@bp.route("/logout")
def logout() -> Any:
    """Log the user out.

    The actual logout is handled by the Firebase client-side SDK.
    This route is for clearing any server-side session info if needed.
    """
    session.clear()
    logout_user()
    flash(AUTH_MESSAGES["LOGOUT_SUCCESS"], "success")
    return redirect(url_for("auth.login"))


@bp.route("/install", methods=["GET", "POST"])
def install() -> Any:
    """Install the application by creating an admin user."""
    db = firestore.client()
    if AuthService.check_admin_exists(db):
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        return AuthService.handle_install_post(db, request.form.to_dict())

    return render_template("install.html")


# TODO: Add type hints for Agent clarity
@bp.route("/change_password", methods=["GET", "POST"])
def change_password() -> Any:
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
        flash(AUTH_MESSAGES["PASSWORD_UPDATED"], "success")
        return redirect(url_for("user.profile"))

    return render_template("change_password.html", user=g.user, form=form)
