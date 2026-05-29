"""Social Credits service for managing virtual currency."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client
    from google.cloud.firestore_v1.transaction import Transaction


class SocialCreditService:
    """Service for managing user social credit balances and transactions."""

    DEFAULT_BALANCE = 100

    @classmethod
    def get_balance(cls, db: Client, user_id: str) -> int:
        """Get the current social credit balance for a user.

        Defaults to 100 if the user exists but hasn't had credits set yet.
        """
        user_ref = db.collection("users").document(user_id)
        doc = user_ref.get()
        if doc.exists:
            data = doc.to_dict() or {}
            return data.get("social_credits", cls.DEFAULT_BALANCE)
        return cls.DEFAULT_BALANCE

    @classmethod
    def adjust_balance(
        cls, db: Client, transaction: Transaction, user_id: str, delta: int
    ) -> int:
        """Adjust a user's balance within a transaction.

        Args:
            db: Firestore client.
            transaction: Firestore transaction.
            user_id: ID of the user.
            delta: Amount to add (positive) or subtract (negative).

        Returns:
            The new balance.

        Raises:
            ValueError: If the user would have a negative balance after adjustment.
        """
        user_ref = db.collection("users").document(user_id)
        doc = user_ref.get(transaction=transaction)

        current_balance = cls.DEFAULT_BALANCE
        if doc.exists:
            data = doc.to_dict() or {}
            current_balance = data.get("social_credits", cls.DEFAULT_BALANCE)

        new_balance = current_balance + delta
        if new_balance < 0:
            raise ValueError(
                f"User {user_id} has insufficient funds for adjustment {delta} "
                f"(current: {current_balance})"
            )

        transaction.update(user_ref, {"social_credits": new_balance})
        return new_balance

    @classmethod
    def transfer(
        cls, db: Client, transaction: Transaction, from_id: str, to_id: str, amount: int
    ) -> None:
        """Transfer social credits between users within a transaction."""
        if amount <= 0:
            raise ValueError("Transfer amount must be positive")

        cls.adjust_balance(db, transaction, from_id, -amount)
        cls.adjust_balance(db, transaction, to_id, amount)
