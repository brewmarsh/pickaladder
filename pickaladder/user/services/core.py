from __future__ import annotations

import os
import secrets
import tempfile
from typing import TYPE_CHECKING, Any, cast

from firebase_admin import auth, firestore, storage
from flask import current_app
from werkzeug.utils import secure_filename

from pickaladder.utils import send_email

from ..helpers import smart_display_name as _smart_display_name

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client


def smart_display_name(user: dict[str, Any]) -> str:
    """Return a smart display name for a user."""
    return _smart_display_name(user)


def update_user_profile(db: Client, user_id: str, update_data: dict[str, Any]) -> None:
    """Update a user's profile in Firestore."""
    user_ref = db.collection("users").document(user_id)
    user_ref.update(update_data)


def get_user_by_id(db: Client, user_id: str) -> dict[str, Any] | None:
    """Fetch a user by their ID."""
    user_ref = db.collection("users").document(user_id)
    user_doc = cast("DocumentSnapshot", user_ref.get())
    if not user_doc.exists:
        return None
    data = user_doc.to_dict()
    if data is None:
        return None
    data["id"] = user_id
    return data


def get_all_users(
    db: Client, exclude_ids: list[str] | None = None, limit: int = 20
) -> list[dict[str, Any]]:
    """Fetch a list of users, excluding given IDs, sorted by date."""
    if exclude_ids is None:
        exclude_ids = []

    users_query = (
        db.collection("users")
        .order_by("createdAt", direction=firestore.Query.DESCENDING)
        .limit(limit + len(exclude_ids))  # Fetch extra in case we exclude users
        .stream()
    )
    users = []
    for doc in users_query:
        if exclude_ids and doc.id in exclude_ids:
            continue
        data = doc.to_dict()
        if data is not None:
            data["id"] = doc.id
            users.append(data)
        if len(users) >= limit:
            break
    return users


def process_profile_update(
    db: Client,
    user_id: str,
    form_data: Any,
    current_user_data: dict[str, Any],
    profile_picture_file: Any = None,
) -> dict[str, Any]:
    """Handle complex profile updates, including email change and verification."""
    new_email = form_data.email.data
    new_username = form_data.username.data
    update_data: dict[str, Any] = {
        "name": form_data.name.data,
        "username": new_username,
    }

    if hasattr(form_data, "dark_mode"):
        update_data["dark_mode"] = bool(form_data.dark_mode.data)

    dupr_id = form_data.dupr_id.data.strip() if form_data.dupr_id.data else None
    update_data["dupr_id"] = dupr_id
    rating = (
        float(form_data.dupr_rating.data)
        if form_data.dupr_rating.data is not None
        else None
    )
    update_data["dupr_rating"] = rating
    update_data["duprRating"] = rating

    # Handle profile picture upload
    if profile_picture_file:
        filename = secure_filename(profile_picture_file.filename or "profile.jpg")
        bucket = storage.bucket()
        blob = bucket.blob(f"profile_pictures/{user_id}/{filename}")

        with tempfile.NamedTemporaryFile(suffix=os.path.splitext(filename)[1]) as tmp:
            profile_picture_file.save(tmp.name)
            blob.upload_from_filename(tmp.name)

        blob.make_public()
        update_data["profilePictureUrl"] = blob.public_url

    # Handle username change
    if new_username != current_user_data.get("username"):
        existing_user = (
            db.collection("users")
            .where("username", "==", new_username)
            .limit(1)
            .stream()
        )
        if len(list(existing_user)) > 0:
            return {
                "success": False,
                "error": "Username already exists. Please choose a different one.",
            }

    # Handle email change
    if new_email != current_user_data.get("email"):
        try:
            auth.update_user(user_id, email=new_email, email_verified=False)
            verification_link = auth.generate_email_verification_link(new_email)
            send_email(
                to=new_email,
                subject="Verify Your New Email Address",
                template="email/verify_email.html",
                user={"username": new_username},
                verification_link=verification_link,
            )
            update_data["email"] = new_email
            update_data["email_verified"] = False
            update_user_profile(db, user_id, update_data)
            return {
                "success": True,
                "info": "Your email has been updated. Please check your new email "
                "address to verify it.",
            }
        except auth.EmailAlreadyExistsError:
            return {"success": False, "error": "That email address is already in use."}
        except Exception as e:
            current_app.logger.error(f"Error updating email: {e}")
            return {
                "success": False,
                "error": "An error occurred while updating your email.",
            }

    update_user_profile(db, user_id, update_data)
    return {"success": True}


def update_settings(
    db: Client, user_id: str, form_data: Any, profile_picture_file: Any = None
) -> dict[str, Any]:
    """Update user settings (username, rating, dark mode, and profile picture)."""
    new_username = form_data.username.data

    # Check for username conflict
    user_ref = db.collection("users").document(user_id)
    current_user_doc = cast("DocumentSnapshot", user_ref.get())
    current_user_data = current_user_doc.to_dict() or {}

    if new_username != current_user_data.get("username"):
        existing_user = (
            db.collection("users")
            .where("username", "==", new_username)
            .limit(1)
            .stream()
        )
        if len(list(existing_user)) > 0:
            return {
                "success": False,
                "error": "Username already exists. Please choose a different one.",
            }

    update_data: dict[str, Any] = {
        "username": new_username,
        "dark_mode": bool(form_data.dark_mode.data),
    }

    if form_data.dupr_rating.data is not None:
        rating = float(form_data.dupr_rating.data)
        update_data["dupr_rating"] = rating
        update_data["duprRating"] = rating  # Maintain compatibility

    if profile_picture_file:
        filename = secure_filename(profile_picture_file.filename or "profile.jpg")
        bucket = storage.bucket()
        blob = bucket.blob(f"profile_pictures/{user_id}/{filename}")

        with tempfile.NamedTemporaryFile(suffix=os.path.splitext(filename)[1]) as tmp:
            profile_picture_file.save(tmp.name)
            blob.upload_from_filename(tmp.name)

        blob.make_public()
        update_data["profilePictureUrl"] = blob.public_url

    user_ref.update(update_data)
    return {"success": True}


def search_users(
    db: Client, current_user_id: str, search_term: str
) -> list[tuple[dict[str, Any], str | None, str | None]]:
    """Search for users and return their friend status with the current user."""
    query: Any = db.collection("users")
    if search_term:
        query = query.where("username", ">=", search_term).where(
            "username", "<=", search_term + "\uf8ff"
        )

    all_users_docs = [
        doc for doc in query.limit(20).stream() if doc.id != current_user_id
    ]

    friends_ref = db.collection("users").document(current_user_id).collection("friends")
    friend_statuses = {doc.id: doc.to_dict() for doc in friends_ref.stream()}

    user_items = []
    for user_doc in all_users_docs:
        user_data = user_doc.to_dict() or {}
        user_data["id"] = user_doc.id
        sent_status = received_status = None
        if friend_data := friend_statuses.get(user_doc.id):
            status = friend_data.get("status")
            if friend_data.get("initiator"):
                sent_status = status
            else:
                received_status = status
        user_items.append((user_data, sent_status, received_status))
    return user_items


def create_invite_token(db: Client, user_id: str) -> str:
    """Generate and store a unique invite token."""
    token = secrets.token_urlsafe(16)
    db.collection("invites").document(token).set(
        {
            "userId": user_id,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "used": False,
        }
    )
    return token


def update_dashboard_profile(
    db: Client, user_id: str, form_data: Any, profile_picture_file: Any = None
) -> None:
    """Update user profile from dashboard form, including image upload."""
    update_data: dict[str, Any] = {"dark_mode": bool(form_data.dark_mode.data)}
    if form_data.dupr_rating.data is not None:
        update_data["duprRating"] = float(form_data.dupr_rating.data)

    if profile_picture_file:
        filename = secure_filename(profile_picture_file.filename or "profile.jpg")
        bucket = storage.bucket()
        blob = bucket.blob(f"profile_pictures/{user_id}/{filename}")
        with tempfile.NamedTemporaryFile(suffix=os.path.splitext(filename)[1]) as tmp:
            profile_picture_file.save(tmp.name)
            blob.upload_from_filename(tmp.name)
        blob.make_public()
        update_data["profilePictureUrl"] = blob.public_url

    update_user_profile(db, user_id, update_data)
