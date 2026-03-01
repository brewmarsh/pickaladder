"""Services for authentication and user registration."""

import re
from typing import Any, cast

from firebase_admin import auth, firestore
from flask import current_app, flash, redirect, session, url_for

from pickaladder.constants.messages import AUTH_MESSAGES
from pickaladder.errors import DuplicateResourceError
from pickaladder.user import UserService
from pickaladder.utils import EmailError, send_email

from .forms import RegisterForm


class AuthService:
    """Service to handle authentication and registration logic."""

    @staticmethod
    def is_username_taken(db: Any, username: str) -> bool:
        """Check if username is already taken in Firestore."""
        taken = (
            db.collection("users")
            .where(filter=firestore.FieldFilter("username", "==", username))
            .limit(1)
            .get()
        )
        return len(list(taken)) > 0

    @staticmethod
    def handle_referral(db: Any, referrer_id: str) -> None:
        """Increment referral count for the referrer."""
        try:
            db.collection("users").document(referrer_id).update(
                {"referral_count": firestore.Increment(1)}
            )
        except Exception as e:
            current_app.logger.error(f"Error incrementing referral count: {e}")

    @staticmethod
    def get_invite_name(db: Any, invite_token: str) -> str | None:
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

    @staticmethod
    def handle_invite_token(db: Any, uid: str, invite_token: str) -> None:
        """Handle invite token by creating friendships and marking token as used."""
        invite_ref = db.collection("invites").document(invite_token)
        invite = invite_ref.get()
        if not invite.exists or invite.to_dict().get("used"):
            return

        inviter_id = invite.to_dict()["userId"]
        batch = db.batch()
        batch.set(
            db.collection("users")
            .document(uid)
            .collection("friends")
            .document(inviter_id),
            {"status": "accepted"},
        )
        batch.set(
            db.collection("users")
            .document(inviter_id)
            .collection("friends")
            .document(uid),
            {"status": "accepted"},
        )
        batch.commit()
        invite_ref.update({"used": True})

    @staticmethod
    def create_firebase_auth_user(email: str, password: str, username: str) -> Any:
        """Create user in Firebase Auth and send verification email."""
        user_record = auth.create_user(
            email=email, password=password, email_verified=False
        )
        verification_link = auth.generate_email_verification_link(email)
        send_email(
            to=email,
            subject="Verify Your Email",
            template="email/verify_email.html",
            user={"username": username},
            verification_link=verification_link,
        )
        return user_record

    @staticmethod
    def prepare_firestore_user_data(
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

    @staticmethod
    def merge_ghost_if_exists(db: Any, uid: str, email: str) -> None:
        """Check for and merge ghost user data if found."""
        user_doc_ref = db.collection("users").document(uid)
        if not (email and UserService.merge_ghost_user(db, user_doc_ref, email)):
            return

        invites = UserService.get_pending_tournament_invites(db, uid)
        if invites:
            session["show_welcome_invites"] = len(invites)

    @staticmethod
    def handle_post_registration(db: Any, uid: str, email: str) -> None:
        """Handle ghost user merging and invite tokens after successful registration."""
        AuthService.merge_ghost_if_exists(db, uid, email)

        invite_token = session.pop("invite_token", None)
        if invite_token:
            AuthService.handle_invite_token(db, uid, invite_token)

    @staticmethod
    def process_registration(form: RegisterForm, username: str, email: str) -> None:
        """Orchestrate the creation of Firebase and Firestore user records."""
        db = firestore.client()
        user_record = AuthService.create_firebase_auth_user(
            email, cast(str, form.password.data), username
        )
        user_data = AuthService.prepare_firestore_user_data(form, email, username)

        if referrer_id := session.pop("referrer_id", None):
            user_data["referred_by"] = referrer_id
            AuthService.handle_referral(db, referrer_id)

        db.collection("users").document(user_record.uid).set(user_data)
        AuthService.handle_post_registration(db, user_record.uid, email)

    @staticmethod
    def handle_registration_error(e: Exception) -> Any:
        """Handle different types of registration errors and flash messages."""
        if isinstance(e, auth.EmailAlreadyExistsError):
            flash(AUTH_MESSAGES["EMAIL_REGISTERED"], "danger")
        elif isinstance(e, EmailError):
            current_app.logger.error(f"Email error during registration: {e}")
            flash(str(e), "danger")
        else:
            current_app.logger.error(f"Error during registration: {e}")
            flash(AUTH_MESSAGES["REGISTRATION_ERROR"], "danger")
        return redirect(url_for("auth.register"))

    @staticmethod
    def execute_registration(form: RegisterForm, username: str, email: str) -> Any:
        """Execute the registration process and handle errors."""
        try:
            AuthService.process_registration(form, username, email)
            flash(
                AUTH_MESSAGES["REGISTRATION_SUCCESS"],
                "success",
            )
            return redirect(url_for("auth.login"))
        except Exception as e:
            return AuthService.handle_registration_error(e)

    @staticmethod
    def generate_unique_username(db: Any, base_username: str) -> str:
        """Generate a unique username by appending a number if the base username exists."""
        username = base_username
        i = 1
        while AuthService.is_username_taken(db, username):
            username = f"{base_username}{i}"
            i += 1
        return username

    @staticmethod
    def prepare_new_user_info(
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
            name = user_record.display_name or (
                email.split("@")[0] if email else "user"
            )
            dupr_rating = None

        if not username:
            effective_name = name or (email.split("@")[0] if email else "user")
            username = re.sub(r"[^a-zA-Z0-9_.]", "", str(effective_name).lower())

        # Always ensure uniqueness, whether it came from registration_data or was derived
        username = AuthService.generate_unique_username(db, username)

        try:
            dupr_val = (
                float(dupr_rating) if dupr_rating and str(dupr_rating).strip() else None
            )
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

    @staticmethod
    def get_or_create_user_profile(
        db: Any, uid: str, registration_data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Retrieve existing user profile or create a new one from Firebase Auth."""
        user_doc_ref = db.collection("users").document(uid)
        user_doc = user_doc_ref.get()

        if user_doc.exists:
            return cast(dict[str, Any], user_doc.to_dict())

        user_info, email = AuthService.prepare_new_user_info(db, uid, registration_data)

        if referrer_id := session.pop("referrer_id", None):
            user_info["referred_by"] = referrer_id
            AuthService.handle_referral(db, referrer_id)

        user_doc_ref.set(user_info)
        AuthService.handle_post_registration(db, uid, email)

        return user_info

    @staticmethod
    def create_admin_account(
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

    @staticmethod
    def check_admin_exists(db: Any) -> bool:
        """Check if any admin user exists in Firestore."""
        admin_query = (
            db.collection("users")
            .where(filter=firestore.FieldFilter("isAdmin", "==", True))
            .limit(1)
            .get()
        )
        return len(list(admin_query)) > 0

    @staticmethod
    def promote_existing_user_to_admin(db: Any, email: str) -> bool:
        """Attempt to promote an existing user to admin if they are not one."""
        try:
            user = auth.get_user_by_email(email)
            doc_ref = db.collection("users").document(user.uid)
            doc = doc_ref.get()
            if not doc.exists or doc.to_dict().get("isAdmin"):
                return False
            doc_ref.update({"isAdmin": True})
            return True
        except auth.UserNotFoundError:
            return False

    @staticmethod
    def handle_install_post(db: Any, form_data: dict[str, Any]) -> Any:
        """Handle POST request for installation."""
        email = form_data.get("email")
        password = form_data.get("password")
        username = form_data.get("username")

        if not all([email, password, username]):
            flash(AUTH_MESSAGES["ADMIN_CREATION_MISSING_FIELDS"], "danger")
            return redirect(url_for("auth.install"))

        try:
            profile_data = {
                "name": form_data.get("name", ""),
                "dupr_rating": form_data.get("dupr_rating"),
            }
            AuthService.create_admin_account(
                db,
                cast(str, email),
                cast(str, password),
                cast(str, username),
                profile_data,
            )
            flash(AUTH_MESSAGES["ADMIN_CREATION_SUCCESS"], "success")
            return redirect(url_for("auth.login"))
        except Exception as e:
            if isinstance(e, auth.EmailAlreadyExistsError):
                if AuthService.promote_existing_user_to_admin(db, cast(str, email)):
                    flash(AUTH_MESSAGES["ADMIN_PROMOTED"], "info")
                    return redirect(url_for("auth.login"))
                raise DuplicateResourceError(
                    "An admin user with this email already exists."
                )

            current_app.logger.error(f"Error during installation: {e}")
            flash(AUTH_MESSAGES["INSTALL_ERROR"], "danger")
            return redirect(url_for("auth.install"))
