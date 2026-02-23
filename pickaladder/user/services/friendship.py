from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from firebase_admin import firestore
from flask import current_app

from .core import _sanitize_user_data

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client


def _fetch_users_by_ids(db: Client, user_ids: list[str]) -> list[dict[str, Any]]:
    """Fetch user documents by a list of IDs and sanitize them."""
    if not user_ids:
        return []
    refs = [db.collection("users").document(uid) for uid in user_ids]
    results = []
    for doc in cast(list["DocumentSnapshot"], db.get_all(refs)):
        if doc.exists and (data := doc.to_dict()) is not None:
            data["id"] = doc.id
            results.append(_sanitize_user_data(data))
    return results


def _get_accepted_friends_query(user_ref: Any, limit: int | None = None) -> Any:
    """Construct a query for accepted friends."""
    query = user_ref.collection("friends").where(
        filter=firestore.FieldFilter("status", "==", "accepted")
    )
    if limit:
        query = query.limit(limit)
    return query


def get_user_friends(
    db: Client, user_id: str, limit: int | None = None
) -> list[dict[str, Any]]:
    """Fetch a user's friends."""
    user_ref = db.collection("users").document(user_id)
    query = _get_accepted_friends_query(user_ref, limit)
    friend_ids = [f.id for f in query.stream()]
    return _fetch_users_by_ids(db, friend_ids)


def _get_friendship_ref(db: Client, user_id: str, target_id: str) -> Any:
    """Get the Firestore reference for a friendship document."""
    return (
        db.collection("users")
        .document(user_id)
        .collection("friends")
        .document(target_id)
    )


def _parse_friendship_status(doc_data: dict[str, Any] | None) -> tuple[bool, bool]:
    """Parse friendship status into is_friend and request_sent booleans."""
    if not doc_data:
        return False, False
    status = doc_data.get("status")
    return status == "accepted", status == "pending"


def get_friendship_info(
    db: Client, current_user_id: str, target_user_id: str
) -> tuple[bool, bool]:
    """Check friendship status between two users."""
    if current_user_id == target_user_id:
        return False, False

    friend_ref = _get_friendship_ref(db, current_user_id, target_user_id)
    doc = cast("DocumentSnapshot", friend_ref.get())
    if not doc.exists:
        return False, False

    return _parse_friendship_status(doc.to_dict())


def get_user_pending_requests(db: Client, user_id: str) -> list[dict[str, Any]]:
    """Fetch pending friend requests where the user is the recipient."""
    user_ref = db.collection("users").document(user_id)
    query = (
        user_ref.collection("friends")
        .where(filter=firestore.FieldFilter("status", "==", "pending"))
        .where(filter=firestore.FieldFilter("initiator", "==", False))
    )
    request_ids = [doc.id for doc in query.stream()]
    return _fetch_users_by_ids(db, request_ids)


def get_user_sent_requests(db: Client, user_id: str) -> list[dict[str, Any]]:
    """Fetch pending friend requests where the user is the initiator."""
    user_ref = db.collection("users").document(user_id)
    query = (
        user_ref.collection("friends")
        .where(filter=firestore.FieldFilter("status", "==", "pending"))
        .where(filter=firestore.FieldFilter("initiator", "==", True))
    )
    request_ids = [doc.id for doc in query.stream()]
    return _fetch_users_by_ids(db, request_ids)


def accept_friend_request(db: Client, user_id: str, requester_id: str) -> bool:
    """Accept a friend request and ensure reciprocal status."""
    try:
        batch = db.batch()
        for uid, friend_id in [(user_id, requester_id), (requester_id, user_id)]:
            ref = (
                db.collection("users")
                .document(uid)
                .collection("friends")
                .document(friend_id)
            )
            batch.update(ref, {"status": "accepted"})
        batch.commit()
        return True
    except Exception as e:
        current_app.logger.error(f"Error accepting friend request: {e}")
        return False


def cancel_friend_request(db: Client, user_id: str, target_user_id: str) -> bool:
    """Cancel or decline a friend request for both users."""
    try:
        batch = db.batch()
        for uid, tid in [(user_id, target_user_id), (target_user_id, user_id)]:
            ref = (
                db.collection("users").document(uid).collection("friends").document(tid)
            )
            batch.delete(ref)
        batch.commit()
        return True
    except Exception as e:
        current_app.logger.error(f"Error cancelling friend request: {e}")
        return False


def send_friend_request(db: Client, user_id: str, friend_id: str) -> bool:
    """Send a friend request and ensure reciprocal pending status."""
    try:
        batch = db.batch()
        # My record
        my_ref = (
            db.collection("users")
            .document(user_id)
            .collection("friends")
            .document(friend_id)
        )
        batch.set(my_ref, {"status": "pending", "initiator": True})
        # Their record
        their_ref = (
            db.collection("users")
            .document(friend_id)
            .collection("friends")
            .document(user_id)
        )
        batch.set(their_ref, {"status": "pending", "initiator": False})
        batch.commit()
        return True
    except Exception as e:
        current_app.logger.error(f"Error sending friend request: {e}")
        return False


def get_friends_page_data(db: Client, user_id: str) -> dict[str, Any]:
    """Fetch all data for the friends list page."""
    f_ref = db.collection("users").document(user_id).collection("friends")

    def get_ids_by_filter(status: str, initiator: bool | None = None) -> list[str]:
        q = f_ref.where(filter=firestore.FieldFilter("status", "==", status))
        if initiator is not None:
            q = q.where(filter=firestore.FieldFilter("initiator", "==", initiator))
        return [doc.id for doc in q.stream()]

    return {
        "friends": _fetch_users_by_ids(db, get_ids_by_filter("accepted")),
        "requests": _fetch_users_by_ids(db, get_ids_by_filter("pending", False)),
        "sent_requests": _fetch_users_by_ids(db, get_ids_by_filter("pending", True)),
    }
