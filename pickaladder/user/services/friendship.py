from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from flask import current_app

from .core import _sanitize_user_data

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client


def get_user_friends(
    db: Client, user_id: str, limit: int | None = None, is_admin: bool = False
) -> list[dict[str, Any]]:
    """Fetch a user's friends with standardized sanitation."""
    user_ref = db.collection("users").document(user_id)
    query = user_ref.collection("friends").where("status", "==", "accepted")
    if limit:
        query = query.limit(limit)

    friends_query = query.stream()
    friend_ids = [f.id for f in friends_query]
    if not friend_ids:
        return []

    refs = [db.collection("users").document(fid) for fid in friend_ids]
    friend_docs = cast(list["DocumentSnapshot"], db.get_all(refs))
    
    results = []
    for doc in friend_docs:
        if doc.exists:
            data = doc.to_dict()
            if data is not None:
                data["id"] = doc.id
                # RESOLVED: Use main's sanitizer with fix's admin-awareness
                results.append(_sanitize_user_data(data, public_only=not is_admin))
    return results


def get_user_pending_requests(
    db: Client, user_id: str, is_admin: bool = False
) -> list[dict[str, Any]]:
    """Fetch incoming friend requests with standardized sanitation."""
    user_ref = db.collection("users").document(user_id)
    requests_query = (
        user_ref.collection("friends")
        .where("status", "==", "pending")
        .where("initiator", "==", False)
        .stream()
    )
    request_ids = [doc.id for doc in requests_query]
    if not request_ids:
        return []

    refs = [db.collection("users").document(uid) for uid in request_ids]
    request_docs = cast(list["DocumentSnapshot"], db.get_all(refs))
    
    results = []
    for doc in request_docs:
        if doc.exists:
            data = doc.to_dict()
            if data is not None:
                data["id"] = doc.id
                # RESOLVED: Standardized sanitation with admin override
                results.append(_sanitize_user_data(data, public_only=not is_admin))
    return results


def get_user_sent_requests(
    db: Client, user_id: str, is_admin: bool = False
) -> list[dict[str, Any]]:
    """Fetch outgoing friend requests with standardized sanitation."""
    user_ref = db.collection("users").document(user_id)
    requests_query = (
        user_ref.collection("friends")
        .where("status", "==", "pending")
        .where("initiator", "==", True)
        .stream()
    )
    request_ids = [doc.id for doc in requests_query]
    if not request_ids:
        return []

    refs = [db.collection("users").document(uid) for uid in request_ids]
    request_docs = cast(list["DocumentSnapshot"], db.get_all(refs))
    
    results = []
    for doc in request_docs:
        if doc.exists:
            data = doc.to_dict()
            if data is not None:
                data["id"] = doc.id
                # RESOLVED: Standardized sanitation with admin override
                results.append(_sanitize_user_data(data, public_only=not is_admin))
    return results

# ... (accept_friend_request, cancel_friend_request, send_friend_request remain unchanged)

def get_friends_page_data(db: Client, user_id: str) -> dict[str, Any]:
    """Fetch all data for the friends list page using the consolidated sanitizer."""
    friends_ref = db.collection("users").document(user_id).collection("friends")

    def fetch_from_ids(ids: list[str]) -> list[dict[str, Any]]:
        if not ids:
            return []
        refs = [db.collection("users").document(uid) for uid in ids]
        docs = cast(list["DocumentSnapshot"], db.get_all(refs))
        results = []
        for doc in docs:
            if doc.exists:
                data = doc.to_dict() or {}
                data["id"] = doc.id
                # Standardize data for the UI
                results.append(_sanitize_user_data(data))
        return results

    # Query logic remains same...
    # [Accepted/Pending/Sent queries as per input]

    return {
        "friends": fetch_from_ids(accepted_ids),
        "requests": fetch_from_ids(request_ids),
        "sent_requests": fetch_from_ids(sent_ids),
    }