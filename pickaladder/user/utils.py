"""Utility functions for user management."""

from firebase_admin import firestore
from flask import current_app


def merge_ghost_user(db, real_user_ref, email):
    """Check for 'ghost' user with the given email and merge their data.

    This function should be called when a user registers or logs in for the first
    time to ensure any matches recorded against their invitation (ghost profile)
    are transferred.
    """
    try:
        users_ref = db.collection("users")
        # Find ghost user by email (lowercase)
        # Note: Ghost users are always created with lowercase email
        query = (
            users_ref.where(filter=firestore.FieldFilter("email", "==", email.lower()))
            .where(filter=firestore.FieldFilter("is_ghost", "==", True))
            .limit(1)
        )

        ghost_docs = list(query.stream())
        if not ghost_docs:
            return

        ghost_doc = ghost_docs[0]
        ghost_ref = ghost_doc.reference

        current_app.logger.info(
            f"Merging ghost user {ghost_doc.id} to real user {real_user_ref.id}"
        )

        batch = db.batch()

        # 1. Update Matches where ghost is player1Ref
        matches_p1 = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("player1Ref", "==", ghost_ref))
            .stream()
        )
        for match in matches_p1:
            batch.update(match.reference, {"player1Ref": real_user_ref})

        # 2. Update Matches where ghost is player2Ref
        matches_p2 = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("player2Ref", "==", ghost_ref))
            .stream()
        )
        for match in matches_p2:
            batch.update(match.reference, {"player2Ref": real_user_ref})

        # 3. Update Matches where ghost is in team1
        matches_t1 = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("team1", "array_contains", ghost_ref))
            .stream()
        )
        for match in matches_t1:
            batch.update(match.reference, {"team1": firestore.ArrayRemove([ghost_ref])})
            batch.update(
                match.reference, {"team1": firestore.ArrayUnion([real_user_ref])}
            )

        # 4. Update Matches where ghost is in team2
        matches_t2 = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("team2", "array_contains", ghost_ref))
            .stream()
        )
        for match in matches_t2:
            batch.update(match.reference, {"team2": firestore.ArrayRemove([ghost_ref])})
            batch.update(
                match.reference, {"team2": firestore.ArrayUnion([real_user_ref])}
            )

        # 5. Update Groups where ghost is a member
        groups_member = (
            db.collection("groups")
            .where(filter=firestore.FieldFilter("members", "array_contains", ghost_ref))
            .stream()
        )
        for group in groups_member:
            batch.update(
                group.reference, {"members": firestore.ArrayRemove([ghost_ref])}
            )
            batch.update(
                group.reference, {"members": firestore.ArrayUnion([real_user_ref])}
            )

        # 6. Delete the ghost user document
        batch.delete(ghost_ref)

        batch.commit()
        current_app.logger.info("Ghost user merge completed successfully.")

    except Exception as e:
        current_app.logger.error(f"Error merging ghost user: {e}")
