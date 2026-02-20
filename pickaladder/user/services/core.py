"""Core service layer for user data operations."""

from __future__ import annotations

import os
import secrets
import tempfile
from typing import TYPE_CHECKING, Any, cast

from firebase_admin import auth, firestore, storage
from flask import current_app
from werkzeug.utils import secure_filename

from pickaladder.utils import mask_email, send_email
from ..helpers import smart_display_name as _smart_display_name

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client


def _sanitize_user_data(
    user_data: dict[str, Any], public_only: bool = True
) -> dict[str, Any]:
    """Filter user data to include only standard fields, handling email masking for ghosts."""
    if not user_data:
        return {}
        
    res = {
        "id": user_data.get("id") or user_data.get("uid"),
        "uid": user_data.get("uid") or user_data.get("id"),
        "name": user_data.get("name"),
        "username": user_data.get("username"),
        "dupr_id": user_data.get("dupr_id"),
        # Combined compatibility from fix branch
        "duprRating": user_data.get("duprRating") or user_data.get("dupr_rating"),
        "dupr_rating": user_data.get("dupr_rating") or user_data.get("duprRating"),
        "profilePictureUrl": user_data.get("profilePictureUrl"),
        "profilePictureThumbnailUrl": user_data.get("profilePictureThumbnailUrl"),
        "isAdmin": user_data.get("isAdmin", False),
        "is_admin": user_data.get("isAdmin", False),
        "is_ghost": user_data.get("is_ghost", False),
    }

    if not public_only:
        res["email"] = user_data.get("email")
        res["email_verified"] = user_data.get("email_verified")
    else:
        # RESOLVED CONFLICT: Apply email masking for ghosts in public views
        if user_data.get("is_ghost") or user_data.get("username", "").startswith("ghost_"):
            if email := user_data.get("email"):
                res["email"] = mask_email(email)

    return res

# ... (smart_display_name, get_avatar_url, update_user_profile, get_user_by_id remain unchanged)

def get_all_users(
    db: Client,
    exclude_ids: list[str] | None = None,
    limit: int = 20,
    public_only: bool = True,
) -> list[dict[str, Any]]:
    """Fetch a list of users using the standardized public_only flag."""
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
        if exclude_ids and doc.id in exclude_ids:
            continue
        data = doc.to_dict()
        if data is not None and "username" in data:
            data["id"] = doc.id
            # RESOLVED: Use consolidated sanitizer from main
            users.append(_sanitize_user_data(data, public_only=public_only))
            
        if len(users) >= limit:
            break
    return users


def search_users(
    db: Client, current_user_id: str, search_term: str, public_only: bool = True
) -> list[tuple[dict[str, Any], str | None, str | None]]:
    """Search for users using the standardized public_only flag."""
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
        
        # RESOLVED: Standardized sanitation
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

# ... (create_invite_token and update_dashboard_profile remain unchanged)