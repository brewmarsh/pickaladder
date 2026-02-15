"""Test configuration and mocks for end-to-end tests."""

from __future__ import annotations

import importlib
import os
import threading
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from mockfirestore import CollectionReference, MockFirestore, Transaction
from mockfirestore.document import DocumentReference, DocumentSnapshot
from mockfirestore.query import Query
from werkzeug.serving import make_server

if TYPE_CHECKING:
    from collections.abc import Generator

# ... (Previous Mock Infrastructure & Patches remain unchanged)

class MockTransaction(Transaction):
    """Mock for firestore.Transaction."""

    def __init__(self, db: EnhancedMockFirestore) -> None:
        """Initialize mock transaction."""
        self.db = db
        self._read_only = False
        self._id = "mock-transaction-id"
        self._max_attempts = 5
        self._retry_id = None

    def _rollback(self) -> None:
        """Mock rollback."""
        pass

    def _begin(self, **kwargs: Any) -> None:
        """Mock begin with simplified signature from main branch."""
        pass

    def _commit(self) -> list[Any]:
        """Mock commit."""
        return []

    def _clean_up(self) -> None:
        """Mock clean up."""
        pass

    def __getattr__(self, name: str) -> Any:
        """Handle missing attributes by returning a no-op or mock."""
        if name.startswith("_"):
            return MagicMock()
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )

    def get(self, ref_or_query: Any, **kwargs: Any) -> Any:
        """Mock get."""
        return ref_or_query.get()

    def set(self, reference: Any, document_data: Any, merge: bool = False) -> None:
        """Mock set."""
        reference.set(document_data, merge=merge)

    def update(
        self, reference: Any, field_updates: dict[str, Any], option: Any = None
    ) -> None:
        """Mock update."""
        reference.update(field_updates)

    def delete(self, reference: Any, option: Any = None) -> None:
        """Mock delete."""
        reference.delete()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

# ... (EnhancedMockFirestore, MockAuthService, and Fixtures remain unchanged)