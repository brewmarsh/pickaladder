from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from flask import current_app

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client


def get_user_friends(
    db: Client, user_id: str, limit: int | None = None
) -> list[dict[str, Any]]:
    """Fetch a user's friends."""
    from pickaladder.user.services import firestore
    user_ref = db.collection("users").document(user_id)
    query = user_ref.collection("friends").where(
        filter=firestore.FieldFilter("status", "==", "accepted")
    )
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
                results.append({"id": doc.id, **data})
    return results


def get_friendship_info(
    db: Client, current_user_id: str, target_user_id: str
) -> tuple[bool, bool]:
    """Check friendship status between two users."""
    friend_request_sent = is_friend = False
    if current_user_id != target_user_id:
        friend_ref = (
            db.collection("users")
            .document(current_user_id)
            .collection("friends")
            .document(target_user_id)
        )
        friend_doc = friend_ref.get()
        if friend_doc.exists:
            data = friend_doc.to_dict()
            if data:
                status = data.get("status")
                if status == "accepted":
                    is_friend = True
                elif status == "pending":
                    friend_request_sent = True
    return is_friend, friend_request_sent


def get_user_pending_requests(db: Client, user_id: str) -> list[dict[str, Any]]:
    """Fetch pending friend requests where the user is the recipient."""
    from pickaladder.user.services import firestore
    user_ref = db.collection("users").document(user_id)
    requests_query = (
        user_ref.collection("friends")
        .where(filter=firestore.FieldFilter("status", "==", "pending"))
        .where(filter=firestore.FieldFilter("initiator", "==", False))
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
                results.append({"id": doc.id, **data})
    return results


def get_user_sent_requests(db: Client, user_id: str) -> list[dict[str, Any]]:
    """Fetch pending friend requests where the user is the initiator."""
    from pickaladder.user.services import firestore
    user_ref = db.collection("users").document(user_id)
    requests_query = (
        user_ref.collection("friends")
        .where(filter=firestore.FieldFilter("status", "==", "pending"))
        .where(filter=firestore.FieldFilter("initiator", "==", True))
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
                results.append({"id": doc.id, **data})
    return results


def accept_friend_request(db: Client, user_id: str, requester_id: str) -> bool:
    """Accept a friend request and ensure reciprocal status."""
    try:
        batch = db.batch()

        # Update status in current user's friend list
        my_friend_ref = (
            db.collection("users")
            .document(user_id)
            .collection("friends")
            .document(requester_id)
        )
        batch.update(my_friend_ref, {"status": "accepted"})

        # Update status in the other user's friend list
        their_friend_ref = (
            db.collection("users")
            .document(requester_id)
            .collection("friends")
            .document(user_id)
        )
        batch.update(their_friend_ref, {"status": "accepted"})

        batch.commit()
        return True
    except Exception as e:
        current_app.logger.error(f"Error accepting friend request: {e}")
        return False


def cancel_friend_request(db: Client, user_id: str, target_user_id: str) -> bool:
    """Cancel or decline a friend request for both users."""
    try:
        batch = db.batch()

        # Delete request from current user's list
        my_friend_ref = (
            db.collection("users")
            .document(user_id)
            .collection("friends")
            .document(target_user_id)
        )
        batch.delete(my_friend_ref)

        # Delete request from the other user's list
        their_friend_ref = (
            db.collection("users")
            .document(target_user_id)
            .collection("friends")
            .document(user_id)
        )
        batch.delete(their_friend_ref)

        batch.commit()
        return True
    except Exception as e:
        current_app.logger.error(f"Error cancelling friend request: {e}")
        return False
