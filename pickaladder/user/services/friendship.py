from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from firebase_admin import firestore

from .core import get_all_users

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client


def get_user_friends(db: Client, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    """Fetch all accepted friends for a user."""
    user_ref = db.collection("users").document(user_id)
    query = user_ref.collection("friends").where("status", "==", "accepted")
    friend_docs = list(query.limit(limit).stream())
    if not friend_docs:
        return []

    friend_refs = [db.collection("users").document(doc.id) for doc in friend_docs]
    docs = db.get_all(friend_refs)
    friends = []
    for doc in docs:
        if doc.exists:
            d = doc.to_dict()
            if d:
                d["id"] = doc.id
                friends.append(d)
    return friends


def get_friendship_info(db: Client, user_id: str, target_id: str) -> tuple[bool, bool]:
    """Check if two users are friends or if a request is pending."""
    friends_ref = db.collection("users").document(user_id).collection("friends")
    doc = cast("DocumentSnapshot", friends_ref.document(target_id).get())
    if doc.exists:
        data = doc.to_dict() or {}
        is_friend = data.get("status") == "accepted"
        friend_request_sent = data.get("status") == "pending" and data.get("initiator")
        return is_friend, bool(friend_request_sent)
    return False, False


def get_user_pending_requests(db: Client, user_id: str) -> list[dict[str, Any]]:
    """Fetch pending friend requests where the user is the recipient."""
    user_ref = db.collection("users").document(user_id)
    query = (
        user_ref.collection("friends")
        .where("status", "==", "pending")
        .where("initiator", "==", False)
    )
    request_docs = list(query.stream())
    if not request_docs:
        return []

    requester_refs = [db.collection("users").document(doc.id) for doc in request_docs]
    docs = db.get_all(requester_refs)
    requesters = []
    for doc in docs:
        if doc.exists:
            d = doc.to_dict()
            if d:
                d["id"] = doc.id
                requesters.append(d)
    return requesters


def get_user_sent_requests(db: Client, user_id: str) -> list[dict[str, Any]]:
    """Fetch pending friend requests where the user is the initiator."""
    user_ref = db.collection("users").document(user_id)
    query = (
        user_ref.collection("friends")
        .where("status", "==", "pending")
        .where("initiator", "==", True)
    )
    request_docs = list(query.stream())
    if not request_docs:
        return []

    target_refs = [db.collection("users").document(doc.id) for doc in request_docs]
    docs = db.get_all(target_refs)
    targets = []
    for doc in docs:
        if doc.exists:
            d = doc.to_dict()
            if d:
                d["id"] = doc.id
                targets.append(d)
    return targets


def send_friend_request(db: Client, sender_id: str, receiver_id: str) -> bool:
    """Create a pending friend request between two users."""
    if sender_id == receiver_id:
        return False

    sender_ref = db.collection("users").document(sender_id)
    receiver_ref = db.collection("users").document(receiver_id)

    batch = db.batch()

    # Sender's record
    batch.set(
        sender_ref.collection("friends").document(receiver_id),
        {
            "status": "pending",
            "initiator": True,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        },
    )

    # Receiver's record
    batch.set(
        receiver_ref.collection("friends").document(sender_id),
        {
            "status": "pending",
            "initiator": False,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        },
    )

    batch.commit()
    return True


def accept_friend_request(db: Client, user_id: str, requester_id: str) -> bool:
    """Accept a pending friend request."""
    user_ref = db.collection("users").document(user_id)
    requester_ref = db.collection("users").document(requester_id)

    # Check if request exists and is pending
    doc = cast(
        "DocumentSnapshot", user_ref.collection("friends").document(requester_id).get()
    )
    if not doc.exists or doc.to_dict().get("status") != "pending":
        return False

    batch = db.batch()

    # Update user's record
    batch.update(
        user_ref.collection("friends").document(requester_id),
        {"status": "accepted", "updatedAt": firestore.SERVER_TIMESTAMP},
    )

    # Update requester's record
    batch.update(
        requester_ref.collection("friends").document(user_id),
        {"status": "accepted", "updatedAt": firestore.SERVER_TIMESTAMP},
    )

    batch.commit()
    return True


def cancel_friend_request(db: Client, user_id: str, target_id: str) -> bool:
    """Cancel or decline a friend request."""
    user_ref = db.collection("users").document(user_id)
    target_ref = db.collection("users").document(target_id)

    batch = db.batch()
    batch.delete(user_ref.collection("friends").document(target_id))
    batch.delete(target_ref.collection("friends").document(user_id))
    batch.commit()
    return True


def get_friends_page_data(db: Client, user_id: str) -> dict[str, Any]:
    """Fetch all data needed for the friends/community page."""

    user_ref = db.collection("users").document(user_id)
    friends_ref = user_ref.collection("friends")

    # Fetch IDs first to minimize data transfer
    friend_ids = [
        doc.id for doc in friends_ref.where("status", "==", "accepted").stream()
    ]

    incoming_ids = [
        doc.id
        for doc in friends_ref.where("status", "==", "pending")
        .where("initiator", "==", False)
        .stream()
    ]

    outgoing_ids = [
        doc.id
        for doc in friends_ref.where("status", "==", "pending")
        .where("initiator", "==", True)
        .stream()
    ]

    # Batch fetch user data
    all_target_ids = list(set(friend_ids + incoming_ids + outgoing_ids))
    users_data = {}
    if all_target_ids:
        user_refs = [db.collection("users").document(uid) for uid in all_target_ids]
        for doc in db.get_all(user_refs):
            if doc.exists:
                d = doc.to_dict()
                if d:
                    d["id"] = doc.id
                    users_data[doc.id] = d

    # Also suggest some people (not friends yet)
    suggested_users = get_all_users(db, exclude_ids=[user_id] + all_target_ids, limit=5)

    return {
        "friends": [users_data[uid] for uid in friend_ids if uid in users_data],
        "incoming_requests": [
            users_data[uid] for uid in incoming_ids if uid in users_data
        ],
        "outgoing_requests": [
            users_data[uid] for uid in outgoing_ids if uid in users_data
        ],
        "suggested_users": suggested_users,
    }
