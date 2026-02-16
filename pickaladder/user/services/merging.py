"""Service for merging ghost users into real user accounts."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from google.cloud.firestore_v1.batch import WriteBatch
    from google.cloud.firestore_v1.client import Client
    from google.cloud.firestore_v1.document import DocumentReference


def merge_ghost_user(db: Client, real_user_id: str, email: str) -> bool:
    """Find a ghost user by email and merge it into the real user account."""
    ghost_query = (
        db.collection("users")
        .where("email", "==", email.lower())
        .where("is_ghost", "==", True)
        .limit(1)
        .stream()
    )

    ghost_docs = list(ghost_query)
    if not ghost_docs:
        return False

    ghost_doc = ghost_docs[0]
    ghost_ref = ghost_doc.reference
    real_user_ref = db.collection("users").document(real_user_id)

    batch = db.batch()
    _migrate_user_references(db, batch, ghost_ref, real_user_ref)

    # Delete the ghost user document
    batch.delete(ghost_ref)

    batch.commit()
    logging.info(f"Merged ghost user {ghost_doc.id} into {real_user_id}")
    return True


def merge_users(db: Client, source_uid: str, target_uid: str) -> None:
    """Merge source user data into target user and delete source."""
    source_ref = db.collection("users").document(source_uid)
    target_ref = db.collection("users").document(target_uid)

    batch = db.batch()
    _migrate_user_references(db, batch, source_ref, target_ref)
    batch.delete(source_ref)
    batch.commit()


def _migrate_user_references(
    db: Client,
    batch: WriteBatch,
    source_ref: DocumentReference,
    target_ref: DocumentReference,
) -> None:
    """Update all Firestore documents referencing the source user."""
    _migrate_singles_matches(db, batch, source_ref, target_ref)
    _migrate_doubles_matches(db, batch, source_ref, target_ref)
    _migrate_groups(db, batch, source_ref, target_ref)
    _migrate_tournaments(db, batch, source_ref, target_ref)


def _migrate_singles_matches(
    db: Client,
    batch: WriteBatch,
    ghost_ref: DocumentReference,
    real_user_ref: DocumentReference,
) -> None:
    """Update singles matches where the user is player 1 or 2."""
    for field in ["player1Ref", "player2Ref"]:
        matches = db.collection("matches").where(field, "==", ghost_ref).stream()
        for match in matches:
            batch.update(match.reference, {field: real_user_ref})


def _migrate_doubles_matches(
    db: Client,
    batch: WriteBatch,
    ghost_ref: DocumentReference,
    real_user_ref: DocumentReference,
) -> None:
    """Update doubles matches where the user is in a team array."""
    for field in ["team1", "team2"]:
        matches = (
            db.collection("matches").where(field, "array_contains", ghost_ref).stream()
        )
        for match in matches:
            data = match.to_dict()
            if not data:
                continue
            old_team = data.get(field, [])
            new_team = [
                real_user_ref if (hasattr(r, "id") and r.id == ghost_ref.id) else r
                for r in old_team
            ]
            batch.update(match.reference, {field: new_team})


def _migrate_groups(
    db: Client,
    batch: WriteBatch,
    ghost_ref: DocumentReference,
    real_user_ref: DocumentReference,
) -> None:
    """Update group memberships."""
    groups = (
        db.collection("groups").where("members", "array_contains", ghost_ref).stream()
    )
    for group in groups:
        data = group.to_dict()
        if not data:
            continue
        old_members = data.get("members", [])
        new_members = [
            real_user_ref if (hasattr(r, "id") and r.id == ghost_ref.id) else r
            for r in old_members
        ]
        batch.update(group.reference, {"members": new_members})


def _migrate_tournaments(
    db: Client,
    batch: WriteBatch,
    ghost_ref: DocumentReference,
    real_user_ref: DocumentReference,
) -> None:
    """Update tournament participants."""
    tournaments = (
        db.collection("tournaments")
        .where("participant_ids", "array_contains", ghost_ref.id)
        .stream()
    )
    for tourney in tournaments:
        data = tourney.to_dict()
        if not data:
            continue

        # Update participant_ids list
        p_ids = data.get("participant_ids", [])
        new_ids = [real_user_ref.id if uid == ghost_ref.id else uid for uid in p_ids]

        # Update participants objects list
        parts = data.get("participants", [])
        new_parts = []
        for p in parts:
            if not p:
                continue
            u_ref = p.get("userRef")
            if u_ref and u_ref.id == ghost_ref.id:
                p["userRef"] = real_user_ref
                # If it was a ghost invite, it might have user_id instead of ref
                if "user_id" in p:
                    p["user_id"] = real_user_ref.id
            new_parts.append(p)

        batch.update(
            tourney.reference, {"participant_ids": new_ids, "participants": new_parts}
        )
