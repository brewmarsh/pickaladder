"""Challenge service for managing formal player-to-player challenges."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from firebase_admin import firestore

from pickaladder.user.services.credits import SocialCreditService

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client
    from google.cloud.firestore_v1.transaction import Transaction


class ChallengeService:
    """Service for managing the lifecycle of competitive challenges."""

    COLLECTION_NAME = "challenges"
    MAX_WAGER = 50
    MAX_ACTIVE_CHALLENGES = 3
    EXPIRATION_HOURS = 48

    @classmethod
    def issue_challenge(
        cls, db: Client, challenger_id: str, challenged_id: str, wager: int
    ) -> str:
        """Issue a new challenge to another player."""
        if challenger_id == challenged_id:
            raise ValueError("You cannot challenge yourself")
        if wager < 0:
            raise ValueError("Wager must be non-negative")
        if wager > cls.MAX_WAGER:
            raise ValueError(f"Wager cannot exceed {cls.MAX_WAGER} credits")

        # Check for active challenge limit
        active_challenges = (
            db.collection(cls.COLLECTION_NAME)
            .where("challenger_id", "==", challenger_id)
            .where("status", "in", ["pending", "accepted"])
            .get()
        )
        if len(active_challenges) >= cls.MAX_ACTIVE_CHALLENGES:
            raise ValueError(
                f"You already have {cls.MAX_ACTIVE_CHALLENGES} active challenges"
            )

        @firestore.transactional
        def create_challenge_tx(transaction: Transaction) -> str:
            # Deduct wager from challenger (escrow)
            SocialCreditService.adjust_balance(db, transaction, challenger_id, -wager)

            challenge_ref = db.collection(cls.COLLECTION_NAME).document()
            challenge_data = {
                "challenger_id": challenger_id,
                "challenged_id": challenged_id,
                "wager_amount": wager,
                "status": "pending",
                "created_at": firestore.SERVER_TIMESTAMP,
                "expires_at": datetime.now(timezone.utc)
                + timedelta(hours=cls.EXPIRATION_HOURS),
            }
            transaction.set(challenge_ref, challenge_data)
            return str(challenge_ref.id)

        return str(create_challenge_tx(db.transaction()))

    @classmethod
    def accept_challenge(cls, db: Client, challenge_id: str, user_id: str) -> None:
        """Accept a pending challenge."""

        @firestore.transactional
        def accept_tx(transaction: Transaction) -> None:
            challenge_ref = db.collection(cls.COLLECTION_NAME).document(challenge_id)
            doc = challenge_ref.get(transaction=transaction)
            if not doc.exists:
                raise ValueError("Challenge not found")

            data = doc.to_dict() or {}
            if data.get("challenged_id") != user_id:
                raise ValueError("Only the challenged user can accept")
            if data.get("status") != "pending":
                raise ValueError(
                    f"Challenge cannot be accepted in status: {data.get('status')}"
                )

            # Check for expiration
            expires_at = data.get("expires_at")
            if expires_at and expires_at < datetime.now(timezone.utc):
                transaction.update(challenge_ref, {"status": "expired"})
                raise ValueError("Challenge has expired")

            wager = data.get("wager_amount", 0)
            # Deduct wager from challenged user (escrow)
            SocialCreditService.adjust_balance(db, transaction, user_id, -wager)

            transaction.update(
                challenge_ref,
                {"status": "accepted", "accepted_at": firestore.SERVER_TIMESTAMP},
            )

        accept_tx(db.transaction())

    @classmethod
    def decline_challenge(cls, db: Client, challenge_id: str, user_id: str) -> None:
        """Decline a pending challenge."""

        @firestore.transactional
        def decline_tx(transaction: Transaction) -> None:
            challenge_ref = db.collection(cls.COLLECTION_NAME).document(challenge_id)
            doc = challenge_ref.get(transaction=transaction)
            if not doc.exists:
                raise ValueError("Challenge not found")

            data = doc.to_dict() or {}
            if data.get("challenged_id") != user_id:
                raise ValueError("Only the challenged user can decline")
            if data.get("status") != "pending":
                raise ValueError(
                    f"Challenge cannot be declined in status: {data.get('status')}"
                )

            wager = data.get("wager_amount", 0)
            # Refund wager to challenger
            SocialCreditService.adjust_balance(
                db, transaction, data.get("challenger_id"), wager
            )

            transaction.update(
                challenge_ref,
                {"status": "declined", "declined_at": firestore.SERVER_TIMESTAMP},
            )

        decline_tx(db.transaction())

    @classmethod
    def resolve_challenge(
        cls, db: Client, challenge_id: str, match_id: str, winner_id: str
    ) -> None:
        """Resolve an accepted challenge based on a match result."""

        @firestore.transactional
        def resolve_tx(transaction: Transaction) -> None:
            challenge_ref = db.collection(cls.COLLECTION_NAME).document(challenge_id)
            doc = challenge_ref.get(transaction=transaction)
            if not doc.exists:
                raise ValueError("Challenge not found")

            data = doc.to_dict() or {}
            if data.get("status") != "accepted":
                return  # Already resolved or not in state to be resolved

            wager = data.get("wager_amount", 0)
            pot = wager * 2

            # Award pot to winner
            SocialCreditService.adjust_balance(db, transaction, winner_id, pot)

            transaction.update(
                challenge_ref,
                {
                    "status": "completed",
                    "match_id": match_id,
                    "winner_id": winner_id,
                    "resolved_at": firestore.SERVER_TIMESTAMP,
                },
            )

        resolve_tx(db.transaction())

    @classmethod
    def find_and_resolve_challenge(
        cls, db: Client, p1_id: str, p2_id: str, match_id: str, winner_id: str
    ) -> None:
        """Find and resolve an accepted challenge between two players."""
        # Find 'accepted' challenge between these two users
        # We need to check both directions for challenger/challenged
        challenges_query = (
            db.collection(cls.COLLECTION_NAME)
            .where("status", "==", "accepted")
            .where("challenger_id", "in", [p1_id, p2_id])
        )

        docs = challenges_query.get()
        for doc in docs:
            data = doc.to_dict()
            challenged_id = data.get("challenged_id")
            if challenged_id in [p1_id, p2_id] and challenged_id != data.get(
                "challenger_id"
            ):
                cls.resolve_challenge(db, doc.id, match_id, winner_id)
                break  # Resolve only one for now (there shouldn't be multiple)

    @classmethod
    def get_user_challenges(cls, db: Client, user_id: str) -> dict[str, list]:
        """Fetch all challenges involving the user, categorized by status."""
        challenges = (
            db.collection(cls.COLLECTION_NAME)
            .where("challenger_id", "==", user_id)
            .get()
        )
        received = (
            db.collection(cls.COLLECTION_NAME)
            .where("challenged_id", "==", user_id)
            .get()
        )

        all_docs = list(challenges) + list(received)

        pending = []
        active = []
        history = []

        # Collect user IDs to fetch names
        uids = set()
        for doc in all_docs:
            data = doc.to_dict()
            uids.add(data.get("challenger_id"))
            uids.add(data.get("challenged_id"))

        # Fetch names in bulk
        names = {}
        if uids:
            user_refs = [db.collection("users").document(uid) for uid in uids if uid]
            for user_doc in db.get_all(user_refs):
                if user_doc.exists:
                    names[user_doc.id] = user_doc.to_dict().get("name", "Unknown")

        for doc in all_docs:
            data = doc.to_dict()
            data["id"] = doc.id
            data["challenger_name"] = names.get(data.get("challenger_id"), "Unknown")
            data["challenged_name"] = names.get(data.get("challenged_id"), "Unknown")
            status = data.get("status")

            if status == "pending":
                pending.append(data)
            elif status == "accepted":
                active.append(data)
            elif status in ["completed", "declined", "expired", "cancelled"]:
                history.append(data)

        # Sort by creation date descending
        pending.sort(key=lambda x: x.get("created_at") or 0, reverse=True)
        active.sort(key=lambda x: x.get("accepted_at") or 0, reverse=True)
        history.sort(
            key=lambda x: x.get("resolved_at") or x.get("created_at") or 0, reverse=True
        )

        return {"pending": pending, "active": active, "history": history}

    @classmethod
    def cancel_challenge(cls, db: Client, challenge_id: str, user_id: str) -> None:
        """Cancel a pending challenge (only by challenger)."""

        @firestore.transactional
        def cancel_tx(transaction: Transaction) -> None:
            challenge_ref = db.collection(cls.COLLECTION_NAME).document(challenge_id)
            doc = challenge_ref.get(transaction=transaction)
            if not doc.exists:
                raise ValueError("Challenge not found")

            data = doc.to_dict() or {}
            if data.get("challenger_id") != user_id:
                raise ValueError("Only the challenger can cancel")
            if data.get("status") != "pending":
                raise ValueError(
                    f"Challenge cannot be cancelled in status: {data.get('status')}"
                )

            wager = data.get("wager_amount", 0)
            # Refund wager to challenger
            SocialCreditService.adjust_balance(db, transaction, user_id, wager)

            transaction.update(
                challenge_ref,
                {"status": "cancelled", "cancelled_at": firestore.SERVER_TIMESTAMP},
            )

        cancel_tx(db.transaction())
