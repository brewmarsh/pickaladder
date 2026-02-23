from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, Any, cast

from firebase_admin import firestore

from ..helpers import smart_display_name as _smart_display_name
from .profile import (
    check_username_availability,
    update_email_address,
    upload_profile_picture,
)

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client


def _sanitize_user_data(
    user_data: dict[str, Any], public_only: bool = True
) -> dict[str, Any]:
    """Filter user data to include only standard public fields."""
    if not user_data:
        return {}
    res = {
        "id": user_data.get("id") or user_data.get("uid"),
        "uid": user_data.get("uid") or user_data.get("id"),
        "name": user_data.get("name"),
        "username": user_data.get("username"),
        "dupr_id": user_data.get("dupr_id"),
        "duprRating": user_data.get("duprRating") or user_data.get("dupr_rating"),
        "dupr_rating": user_data.get("dupr_rating") or user_data.get("duprRating"),
        "profilePictureUrl": user_data.get("profilePictureUrl"),
        "profilePictureThumbnailUrl": user_data.get("profilePictureThumbnailUrl"),
        "isAdmin": user_data.get("isAdmin", False),
        "is_admin": user_data.get("isAdmin", False),
    }
    if not public_only:
        res["email"] = user_data.get("email")
        res["email_verified"] = user_data.get("email_verified")
    return res


def smart_display_name(user: dict[str, Any]) -> str:
    """Return a smart display name for a user."""
    return _smart_display_name(user)


def get_avatar_url(user_data: dict[str, Any]) -> str:
    """Get the avatar URL for a user, using a fallback if not present."""
    if url := user_data.get("profilePictureUrl"):
        return str(url)
    seed = user_data.get("username") or user_data.get("email") or "User"
    return f"https://api.dicebear.com/9.x/avataaars/svg?seed={seed}"


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
    data["uid"] = user_id
    return data


def _process_user_doc(
    doc: DocumentSnapshot, exclude_ids: list[str], public_only: bool
) -> dict[str, Any] | None:
    """Process a user document snapshot into sanitized data."""
    if doc.id in exclude_ids:
        return None
    data = doc.to_dict()
    if data is not None and "username" in data:
        data["id"] = doc.id
        return _sanitize_user_data(data, public_only=public_only)
    return None


def get_all_users(
    db: Client,
    exclude_ids: list[str] | None = None,
    limit: int = 20,
    public_only: bool = True,
) -> list[dict[str, Any]]:
    """Fetch a list of users, excluding given IDs, sorted by date."""
    if exclude_ids is None:
        exclude_ids = []

    try:
        users_query = (
            db.collection("users")
            .order_by("createdAt", direction=firestore.Query.DESCENDING)
            .limit(limit + len(exclude_ids))
            .stream()
        )
    except KeyError:
        users_query = db.collection("users").stream()

    users = []
    for doc in users_query:
        if processed := _process_user_doc(doc, exclude_ids, public_only):
            users.append(processed)
        if len(users) >= limit:
            break
    return users


def _map_dupr_data(form_data: Any) -> tuple[str | None, float | None]:
    """Extract DUPR ID and rating from form data."""
    dupr_id = None
    if hasattr(form_data, "dupr_id") and form_data.dupr_id and form_data.dupr_id.data:
        dupr_id = form_data.dupr_id.data.strip()

    rating = None
    if (
        hasattr(form_data, "dupr_rating")
        and form_data.dupr_rating
        and form_data.dupr_rating.data is not None
    ):
        rating = float(form_data.dupr_rating.data)
    return dupr_id, rating


def _handle_profile_picture(
    user_id: str, update_data: dict[str, Any], profile_picture_file: Any
) -> None:
    """Handle profile picture upload and update the update_data dictionary."""
    if not profile_picture_file:
        return

    url = upload_profile_picture(user_id, profile_picture_file)
    if url:
        update_data["profilePictureUrl"] = url
        update_data["profilePictureThumbnailUrl"] = None


def _validate_username_change(
    db: Client, new_username: str, current_username: str | None
) -> dict[str, Any] | None:
    """Check if the new username is available if it has changed."""
    if new_username != current_username:
        if not check_username_availability(db, new_username):
            return {
                "success": False,
                "error": "Username already exists. Please choose a different one.",
            }
    return None


def _handle_email_change(
    db: Client,
    new_email: str,
    username: str,
    update_data: dict[str, Any],
    current_user_data: dict[str, Any],
) -> dict[str, Any] | None:
    """Handle email change logic and verification."""
    if new_email != current_user_data.get("email"):
        user_id = cast(str, current_user_data.get("id") or current_user_data.get("uid"))
        success, message = update_email_address(
            db, user_id, new_email, username, update_data
        )
        if success:
            if current_user_data is not None and hasattr(current_user_data, "update"):
                current_user_data.update(update_data)
            return {"success": True, "info": message}
        return {"success": False, "error": message}
    return None


def process_profile_update(
    db: Client,
    user_id: str,
    form_data: Any,
    current_user_data: dict[str, Any],
    profile_picture_file: Any = None,
) -> dict[str, Any]:
    """Handle complex profile updates, including email change and verification."""
    new_username = form_data.username.data
    update_data: dict[str, Any] = {
        "name": form_data.name.data,
        "username": new_username,
    }
    if hasattr(form_data, "dark_mode") and form_data.dark_mode:
        update_data["dark_mode"] = bool(form_data.dark_mode.data)

    dupr_id, rating = _map_dupr_data(form_data)
    update_data.update(
        {"dupr_id": dupr_id, "dupr_rating": rating, "duprRating": rating}
    )

    _handle_profile_picture(user_id, update_data, profile_picture_file)

    if err := _validate_username_change(
        db, new_username, current_user_data.get("username")
    ):
        return err

    email_res = _handle_email_change(
        db, form_data.email.data, new_username, update_data, current_user_data
    )
    if email_res:
        return email_res

    update_user_profile(db, user_id, update_data)
    if current_user_data is not None and hasattr(current_user_data, "update"):
        current_user_data.update(update_data)

    return {"success": True}


def _get_current_user_data(db: Client, user_id: str) -> dict[str, Any]:
    """Fetch current user data from Firestore."""
    user_ref = db.collection("users").document(user_id)
    doc = cast("DocumentSnapshot", user_ref.get())
    return doc.to_dict() or {}


def _map_settings_update_data(form_data: Any) -> dict[str, Any]:
    """Map form data to Firestore update dictionary."""
    update_data: dict[str, Any] = {"username": form_data.username.data}
    if hasattr(form_data, "dark_mode") and form_data.dark_mode:
        update_data["dark_mode"] = bool(form_data.dark_mode.data)
    if hasattr(form_data, "name") and form_data.name and form_data.name.data:
        update_data["name"] = form_data.name.data

    dupr_id, rating = _map_dupr_data(form_data)
    if dupr_id:
        update_data["dupr_id"] = dupr_id
    if rating is not None:
        update_data.update({"dupr_rating": rating, "duprRating": rating})

    return update_data


def update_settings(
    db: Client,
    user_id: str,
    form_data: Any,
    current_user_data: dict[str, Any] | None = None,
    profile_picture_file: Any = None,
) -> dict[str, Any]:
    """Update user settings (username, rating, dark mode, and profile picture)."""
    if current_user_data is None:
        current_user_data = _get_current_user_data(db, user_id)

    if err := _validate_username_change(
        db, form_data.username.data, current_user_data.get("username")
    ):
        return err

    update_data = _map_settings_update_data(form_data)
    _handle_profile_picture(user_id, update_data, profile_picture_file)

    if hasattr(form_data, "email") and form_data.email.data:
        email_res = _handle_email_change(
            db,
            form_data.email.data,
            form_data.username.data,
            update_data,
            current_user_data,
        )
        if email_res:
            return email_res

    db.collection("users").document(user_id).update(update_data)
    if current_user_data is not None and hasattr(current_user_data, "update"):
        current_user_data.update(update_data)

    return {"success": True}


def search_users(
    db: Client, current_user_id: str, search_term: str, public_only: bool = True
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
        sanitized_data = _sanitize_user_data(user_data, public_only=public_only)
        sent_status = received_status = None
        if friend_data := friend_statuses.get(user_doc.id):
            status = friend_data.get("status")
            if friend_data.get("initiator"):
                sent_status = status
            else:
                received_status = status
        user_items.append((sanitized_data, sent_status, received_status))
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
    db: Client,
    user_id: str,
    form_data: Any,
    current_user_data: dict[str, Any] | None = None,
    profile_picture_file: Any = None,
) -> None:
    """Update user profile from dashboard form, including image upload."""
    update_data: dict[str, Any] = {"dark_mode": bool(form_data.dark_mode.data)}
    if form_data.dupr_rating.data is not None:
        rating = float(form_data.dupr_rating.data)
        update_data.update({"duprRating": rating, "dupr_rating": rating})

    _handle_profile_picture(user_id, update_data, profile_picture_file)

    update_user_profile(db, user_id, update_data)
    if current_user_data is not None and hasattr(current_user_data, "update"):
        current_user_data.update(update_data)
