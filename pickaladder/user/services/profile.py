"""Service for user profile management."""

from __future__ import annotations

import os
import tempfile
from typing import TYPE_CHECKING, Any

from firebase_admin import auth, storage
from flask import current_app
from werkzeug.utils import secure_filename

from pickaladder.utils import EmailError, send_email

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client
    from werkzeug.datastructures import FileStorage


def check_username_availability(db: Client, username: str) -> bool:
    """Check if a username is available."""
    users_ref = db.collection("users")
    existing_user = users_ref.where("username", "==", username).limit(1).stream()
    return len(list(existing_user)) == 0


def update_email_address(
    db: Client,
    user_id: str,
    new_email: str,
    new_username: str,
    update_data: dict[str, Any],
) -> tuple[bool, str]:
    """Update a user's email address and send verification email.

    Returns:
        tuple[bool, str]: (success, message)
    """
    try:
        auth.update_user(user_id, email=new_email, email_verified=False)
        verification_link = auth.generate_email_verification_link(new_email)
        # Update Firestore MUST happen if auth.update_user succeeded
        update_data["email"] = new_email
        update_data["email_verified"] = False
        db.collection("users").document(user_id).update(update_data)

        try:
            send_email(
                to=new_email,
                subject="Verify Your New Email Address",
                template="email/verify_email.html",
                user={"username": new_username},
                verification_link=verification_link,
            )
        except EmailError as e:
            current_app.logger.error(f"Email error updating email: {e}")
            return (
                True,
                "Your email has been updated in our records, but we couldn't send a verification email. Please contact support.",
            )

        return (
            True,
            "Your email has been updated. Please check your new email address to verify it.",
        )
    except auth.EmailAlreadyExistsError:
        return False, "That email address is already in use."
    except Exception as e:
        current_app.logger.error(f"Error updating email: {e}")
        return False, "An error occurred while updating your email."


def upload_profile_picture(user_id: str, file_storage: FileStorage) -> str | None:
    """Upload a profile picture to Firebase Storage and return the public URL."""
    try:
        filename = secure_filename(file_storage.filename or "profile.jpg")
        bucket = storage.bucket()
        blob = bucket.blob(f"profile_pictures/{user_id}/{filename}")

        with tempfile.NamedTemporaryFile(
            suffix=os.path.splitext(filename)[1]
        ) as temp_file:
            file_storage.save(temp_file.name)
            blob.upload_from_filename(temp_file.name)

        blob.make_public()
        return blob.public_url
    except Exception as e:
        current_app.logger.error(f"Error uploading profile picture: {e}")
        return None
