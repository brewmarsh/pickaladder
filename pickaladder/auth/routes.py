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


# TODO: Add type hints for Agent clarity
def _is_username_taken(db: Any, username: str) -> bool:
    """Check if username is already taken in Firestore."""
    taken = (
        db.collection("users")
        .where(filter=firestore.FieldFilter("username", "==", username))
        .limit(1)
        .get()
    )
    return len(list(taken)) > 0


def _handle_referral(db: Any, referrer_id: str) -> None:
    """Increment referral count for the referrer."""
    try:
        db.collection("users").document(referrer_id).update(
            {"referral_count": firestore.Increment(1)}
        )
    except Exception as e:
        current_app.logger.error(f"Error incrementing referral count: {e}")


def _get_invite_name(db: Any, invite_token: str) -> str | None:
    """Retrieve the inviter's name from an invite token."""
    invite_ref = db.collection("invites").document(invite_token)
    invite = invite_ref.get()
    if not invite.exists:
        return None

    inviter_id = invite.to_dict().get("userId")
    if not inviter_id:
        return None

    inviter_doc = db.collection("users").document(inviter_id).get()
    if not inviter_doc.exists:
        return None

    return inviter_doc.to_dict().get("name")


def _handle_invite_token(db: Any, uid: str, invite_token: str) -> None:
    """Handle invite token by creating friendships and marking token as used."""
    invite_ref = db.collection("invites").document(invite_token)
    invite = invite_ref.get()
    if not invite.exists or invite.to_dict().get("used"):
        return

    inviter_id = invite.to_dict()["userId"]
    batch = db.batch()
    batch.set(
        db.collection("users").document(uid).collection("friends").document(inviter_id),
        {"status": "accepted"},
    )
    batch.set(
        db.collection("users").document(inviter_id).collection("friends").document(uid),
        {"status": "accepted"},
    )
    batch.commit()
    invite_ref.update({"used": True})


def _create_firebase_auth_user(email: str, password: str, username: str) -> Any:
    """Create user in Firebase Auth and send verification email."""
    user_record = auth.create_user(email=email, password=password, email_verified=False)
    verification_link = auth.generate_email_verification_link(email)
    send_email(
        to=email,
        subject="Verify Your Email",
        template="email/verify_email.html",
        user={"username": username},
        verification_link=verification_link,
    )
    return user_record


def _prepare_firestore_user_data(
    form: RegisterForm, email: str, username: str
) -> dict[str, Any]:
    """Prepare the initial user document data for Firestore."""
    return {
        "username": username,
        "email": email,
        "name": form.name.data,
        "duprRating": float(form.dupr_rating.data)
        if form.dupr_rating.data is not None
        else 0.0,
        "isAdmin": False,
        "createdAt": firestore.SERVER_TIMESTAMP,
    }


def _merge_ghost_if_exists(db: Any, uid: str, email: str) -> None:
    """Check for and merge ghost user data if found."""
    user_doc_ref = db.collection("users").document(uid)
    if not (email and UserService.merge_ghost_user(db, user_doc_ref, email)):
        return

    invites = UserService.get_pending_tournament_invites(db, uid)
    if invites:
        session["show_welcome_invites"] = len(invites)


def _handle_post_registration(db: Any, uid: str, email: str) -> None:
    """Handle ghost user merging and invite tokens after successful registration."""
    _merge_ghost_if_exists(db, uid, email)

    invite_token = session.pop("invite_token", None)
    if invite_token:
        _handle_invite_token(db, uid, invite_token)


def _process_registration(form: RegisterForm, username: str, email: str) -> None:
    """Orchestrate the creation of Firebase and Firestore user records."""
    db = firestore.client()
    user_record = _create_firebase_auth_user(
        email, cast(str, form.password.data), username
    )
    user_data = _prepare_firestore_user_data(form, email, username)

    if referrer_id := session.pop("referrer_id", None):
        user_data["referred_by"] = referrer_id
        _handle_referral(db, referrer_id)

    db.collection("users").document(user_record.uid).set(user_data)
    _handle_post_registration(db, user_record.uid, email)


def _handle_registration_error(e: Exception) -> Any:
    """Handle different types of registration errors and flash messages."""
    if isinstance(e, auth.EmailAlreadyExistsError):
        flash(AUTH_MESSAGES["EMAIL_REGISTERED"], "danger")
    elif isinstance(e, EmailError):
        current_app.logger.error(f"Email error during registration: {e}")
        flash(str(e), "danger")
    else:
        current_app.logger.error(f"Error during registration: {e}")
        flash(AUTH_MESSAGES["REGISTRATION_ERROR"], "danger")
    return redirect(url_for(".register"))


def _execute_registration(form: RegisterForm, username: str, email: str) -> Any:
    """Execute the registration process and handle errors."""
    try:
        _process_registration(form, username, email)
        flash(
            AUTH_MESSAGES["REGISTRATION_SUCCESS"],
            "success",
        )
        return redirect(url_for(".login", next=request.args.get("next")))
    except Exception as e:
        return _handle_registration_error(e)


@bp.route("/check_username")
def check_username() -> Any:
    """Check if a username is available (Ajax)."""
    username = request.args.get("username", "").strip()
    if not username:
        return jsonify({"available": False, "message": "Username is required."})

    db = firestore.client()
    is_taken = _is_username_taken(db, username)
    return jsonify({"available": not is_taken})


@bp.route("/register", methods=["GET", "POST"])
def register() -> Any:
    """Register a new user."""
    db = firestore.client()
    invite_token = request.args.get("invite_token") or session.get("invite_token")
    invite_name = None

    if invite_token:
        session["invite_token"] = invite_token
        invite_name = _get_invite_name(db, invite_token)

    form = RegisterForm()
    if not form.validate_on_submit():
        return render_template(
            "register.html", form=form, invite_name=invite_name, invite_token=invite_token
        )

    username = cast(str, form.username.data)
    email = cast(str, form.email.data)

    if _is_username_taken(db, username):
        flash(AUTH_MESSAGES["USERNAME_EXISTS"], "danger")
        return redirect(url_for(".register"))

    return _execute_registration(form, username, email)


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
def _prepare_new_user_info(
    db: Any, uid: str, registration_data: dict[str, Any] | None = None
) -> tuple[dict[str, Any], str]:
    """Extract and prepare initial info for a new user from Firebase Auth."""
    user_record = auth.get_user(uid)
    email = user_record.email

    if registration_data:
        username = registration_data.get("username")
        name = registration_data.get("name")
        dupr_rating = registration_data.get("duprRating")
    else:
        username = None
        name = user_record.display_name or email.split("@")[0]
        dupr_rating = None

    if not username:
        base_username = re.sub(r"[^a-zA-Z0-9_.]", "", name.lower())
        username = _generate_unique_username(db, base_username)

    try:
        dupr_val = float(dupr_rating) if dupr_rating and str(dupr_rating).strip() else None
    except (ValueError, TypeError):
        dupr_val = None

    user_info = {
        "username": username,
        "email": email,
        "name": name,
        "duprRating": dupr_val,
        "isAdmin": False,
        "createdAt": firestore.SERVER_TIMESTAMP,
    }
    return user_info, email


def _get_or_create_user_profile(
    db: Any, uid: str, registration_data: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Retrieve existing user profile or create a new one from Firebase Auth."""
    user_doc_ref = db.collection("users").document(uid)
    user_doc = user_doc_ref.get()

    if user_doc.exists:
        return cast(dict[str, Any], user_doc.to_dict())

    user_info, email = _prepare_new_user_info(db, uid, registration_data)

    if referrer_id := session.pop("referrer_id", None):
        user_info["referred_by"] = referrer_id
        _handle_referral(db, referrer_id)

    user_doc_ref.set(user_info)

    _handle_post_registration(db, uid, email)

    return user_info


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

        user_info = _get_or_create_user_profile(db, uid, registration_data)
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


# TODO: Add type hints for Agent clarity
def _create_admin_account(
    db: Any,
    email: str,
    password: str,
    username: str,
    profile_data: dict[str, Any],
) -> str:
    """Create admin user in Firebase Auth and Firestore, and set initial settings."""
    admin_user_record = auth.create_user(
        email=email, password=password, email_verified=True
    )

    admin_doc_ref = db.collection("users").document(admin_user_record.uid)
    admin_doc_ref.set(
        {
            "username": username,
            "email": email,
            "name": profile_data.get("name", ""),
            "duprRating": float(profile_data.get("dupr_rating") or 0),
            "isAdmin": True,
            "createdAt": firestore.SERVER_TIMESTAMP,
        }
    )

    settings_ref = db.collection("settings").document("enforceEmailVerification")
    settings_ref.set({"value": True})

    return cast(str, admin_user_record.uid)


def _is_user_non_admin(user_doc: Any) -> bool:
    """Check if the user exists and is not an admin."""
    if not user_doc.exists:
        return False
    return not user_doc.to_dict().get("isAdmin")


def _fetch_user_doc_ref_by_email(db: Any, email: str) -> Any:
    """Fetch user document reference from Firestore using email via Firebase Auth."""
    user = auth.get_user_by_email(email)
    return db.collection("users").document(user.uid)


def _promote_existing_user_to_admin(db: Any, email: str) -> bool:
    """Attempt to promote an existing user to admin if they are not one."""
    try:
        doc_ref = _fetch_user_doc_ref_by_email(db, email)
        doc = doc_ref.get()
        if not _is_user_non_admin(doc):
            return False
        doc_ref.update({"isAdmin": True})
        return True
    except auth.UserNotFoundError:
        return False


def _check_admin_exists(db: Any) -> bool:
    """Check if any admin user exists in Firestore."""
    admin_query = (
        db.collection("users")
        .where(filter=firestore.FieldFilter("isAdmin", "==", True))
        .limit(1)
        .get()
    )
    return len(list(admin_query)) > 0


def _handle_install_error(db: Any, email: str, e: Exception) -> Any:
    """Handle exceptions during installation."""
    if isinstance(e, auth.EmailAlreadyExistsError):
        if _promote_existing_user_to_admin(db, email):
            flash(AUTH_MESSAGES["ADMIN_PROMOTED"], "info")
            return redirect(url_for("auth.login"))
        raise DuplicateResourceError("An admin user with this email already exists.")

    current_app.logger.error(f"Error during installation: {e}")
    flash(AUTH_MESSAGES["INSTALL_ERROR"], "danger")
    return redirect(url_for(".install"))


def _handle_install_post(db: Any) -> Any:
    """Handle POST request for installation."""
    email = request.form.get("email")
    password = request.form.get("password")
    username = request.form.get("username")

    if not all([email, password, username]):
        flash(AUTH_MESSAGES["ADMIN_CREATION_MISSING_FIELDS"], "danger")
        return redirect(url_for(".install"))

    try:
        profile_data = {
            "name": request.form.get("name", ""),
            "dupr_rating": request.form.get("dupr_rating"),
        }
        _create_admin_account(
            db,
            cast(str, email),
            cast(str, password),
            cast(str, username),
            profile_data,
        )
        flash(AUTH_MESSAGES["ADMIN_CREATION_SUCCESS"], "success")
        return redirect(url_for("auth.login"))
    except Exception as e:
        return _handle_install_error(db, cast(str, email), e)


@bp.route("/install", methods=["GET", "POST"])
def install() -> Any:
    """Install the application by creating an admin user."""
    db = firestore.client()
    if _check_admin_exists(db):
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        return _handle_install_post(db)

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
