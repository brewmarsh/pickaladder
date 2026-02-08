from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

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
    from pickaladder.user.services import firestore  # noqa: PLC0415

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
