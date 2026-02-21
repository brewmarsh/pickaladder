from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from firebase_admin import auth, firestore
from flask import current_app

from pickaladder.errors import DuplicateResourceError
from pickaladder.user import UserService
from pickaladder.utils import send_email

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client


class AuthService:
    """Service class for authentication-related operations."""

    @staticmethod
    def register_user(  # noqa: PLR0913
        db: Client,
        email: str,
        password: str,
        username: str,
        name: str,
        dupr_rating: float = 0.0,
        referrer_id: str | None = None,
        invite_token: str | None = None,
    ) -> dict[str, Any]:
        """Register a new user, create Firebase Auth record and Firestore document.

        Args:
            db: Firestore client.
            email: User's email.
            password: User's password.
            username: User's chosen username.
            name: User's full name.
            dupr_rating: User's DUPR rating.
            referrer_id: UID of the user who referred this new user.
            invite_token: Token from an invitation.

        Returns:
            A dictionary containing the new user's UID and metadata.

        Raises:
            DuplicateResourceError: If the username is already taken.
            auth.EmailAlreadyExistsError: If the email is already registered in Firebase Auth.
        """
        # 1. Check if username is already taken in Firestore
        users_ref = db.collection("users")
        taken = (
            users_ref.where(filter=firestore.FieldFilter("username", "==", username))
            .limit(1)
            .get()
        )
        if len(list(taken)) > 0:
            raise DuplicateResourceError(
                "Username already exists. Please choose a different one."
            )

        # 2. Create user in Firebase Authentication
        # This may raise auth.EmailAlreadyExistsError which we let bubble up
        user_record = auth.create_user(
            email=email, password=password, email_verified=False
        )

        # 3. Send email verification
        try:
            verification_link = auth.generate_email_verification_link(email)
            send_email(
                to=email,
                subject="Verify Your Email",
                template="email/verify_email.html",
                user={"username": username},
                verification_link=verification_link,
            )
        except Exception as e:
            # We log the error but continue with user creation in Firestore
            # as the Auth record is already created.
            current_app.logger.error(f"Email error during registration: {e}")

        # 4. Create user document in Firestore
        user_doc_ref = db.collection("users").document(user_record.uid)
        user_data = {
            "username": username,
            "email": email,
            "name": name,
            "duprRating": dupr_rating,
            "isAdmin": False,
            "createdAt": firestore.SERVER_TIMESTAMP,
        }

        if referrer_id:
            user_data["referred_by"] = referrer_id

        user_doc_ref.set(user_data)

        # 5. Handle referral increment
        if referrer_id:
            try:
                db.collection("users").document(referrer_id).update(
                    {"referral_count": firestore.Increment(1)}
                )
            except Exception as e:
                current_app.logger.error(f"Error incrementing referral count: {e}")

        # 6. Check for ghost user merge
        merged = False
        pending_invites_count = 0
        if UserService.merge_ghost_user(db, user_doc_ref, email):
            merged = True
            # Check for tournament invites to show welcome toast
            invites = UserService.get_pending_tournament_invites(db, user_record.uid)
            if invites:
                pending_invites_count = len(invites)

        # 7. Handle invite token for friendship
        if invite_token:
            invite_ref = db.collection("invites").document(invite_token)
            invite = cast("DocumentSnapshot", invite_ref.get())
            if invite.exists:
                invite_data = invite.to_dict()
                if invite_data and not invite_data.get("used"):
                    inviter_id = invite_data["userId"]
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

        return {
            "uid": user_record.uid,
            "merged": merged,
            "pending_invites_count": pending_invites_count,
        }
