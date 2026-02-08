"""Task service for groups."""

from __future__ import annotations

import sys
import threading
from typing import TYPE_CHECKING, Any

from firebase_admin import firestore

if TYPE_CHECKING:
    from flask import Flask

from pickaladder.utils import send_email

FIRESTORE_BATCH_LIMIT = 400


def send_invite_email_background(
    app: Flask, invite_token: str, email_data: dict[str, Any]
) -> None:
    """Send an invite email in a background thread."""

    def task() -> None:
        """Perform the email sending task in the background."""
        with app.app_context():
            db = firestore.client()
            invite_ref = db.collection("group_invites").document(invite_token)
            try:
                # We need to render the template inside the app context if it
                # wasn't pre-rendered. send_email takes a template name and
                # kwargs.
                send_email(**email_data)
                invite_ref.update(
                    {"status": "sent", "last_error": firestore.DELETE_FIELD}
                )
            except Exception as e:
                # Log the full exception to stderr so it shows up in Docker logs
                print(f"ERROR: Background invite email failed: {e}", file=sys.stderr)
                # Store the error message
                invite_ref.update({"status": "failed", "last_error": str(e)})

    thread = threading.Thread(target=task)
    thread.start()


def friend_group_members(db: Any, group_id: str, new_member_ref: Any) -> None:
    """Automatically create friend relationships between group members.

    Automatically create friend relationships between the new member and existing
    group members.
    """
    group_ref = db.collection("groups").document(group_id)
    group_doc = group_ref.get()
    if not group_doc.exists:
        return

    group_data = group_doc.to_dict()
    member_refs = group_data.get("members", [])

    if not member_refs:
        return

    batch = db.batch()
    new_member_id = new_member_ref.id
    operation_count = 0

    for member_ref in member_refs:
        if member_ref.id == new_member_id:
            continue

        # Add friend for new member
        new_member_friend_ref = new_member_ref.collection("friends").document(
            member_ref.id
        )
        # Add friend for existing member
        existing_member_friend_ref = member_ref.collection("friends").document(
            new_member_id
        )

        batch.set(
            new_member_friend_ref,
            {"status": "accepted", "initiator": True},
            merge=True,
        )
        batch.set(
            existing_member_friend_ref,
            {"status": "accepted", "initiator": False},
            merge=True,
        )
        operation_count += 2

        # Commit batch if it gets too large (Firestore limit is 500)
        if operation_count >= FIRESTORE_BATCH_LIMIT:
            batch.commit()
            batch = db.batch()
            operation_count = 0

    if operation_count > 0:
        try:
            batch.commit()
        except Exception as e:
            print(f"Error friending group members: {e}", file=sys.stderr)
