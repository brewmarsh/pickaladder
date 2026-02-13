from typing import Any

from google.cloud.firestore_v1.document import DocumentReference
from google.cloud.firestore_v1.transaction import Transaction

# Assuming EnhancedMockFirestore is defined earlier in the file...


class MockBatch:
    """Mock for firestore.WriteBatch."""

    def __init__(self, client: Any) -> None:
        """Initialize mock batch."""
        self.client = client
        self.ops: list[Any] = []

    def set(
        self, doc_ref: DocumentReference, data: dict[str, Any], merge: bool = False
    ) -> None:
        """Mock set."""
        self.ops.append(("set", doc_ref, data, merge))

    def update(self, doc_ref: DocumentReference, data: dict[str, Any]) -> None:
        """Mock update."""
        self.ops.append(("update", doc_ref, data))

    def delete(self, doc_ref: DocumentReference) -> None:
        """Mock delete."""
        self.ops.append(("delete", doc_ref))

    def commit(self) -> None:
        """Mock commit."""
        for op in self.ops:
            if op[0] == "set":
                op[1].set(op[2], merge=op[3])
            elif op[0] == "update":
                op[1].update(op[2])
            elif op[0] == "delete":
                op[1].delete()
        self.ops = []


class MockTransaction(Transaction):
    """Mock for firestore.Transaction."""

    def __init__(self, db: Any) -> None:
        """Initialize mock transaction."""
        # Note: We don't call super().__init__ because it requires a live client
        self.db = db
        self._read_only = False
        self._id = "mock-transaction-id"  # type: ignore
        self._max_attempts = 5

    def _rollback(self) -> None:
        """Mock rollback method to prevent TypeError in library calls."""
        pass

    def get(self, ref_or_query: Any) -> Any:  # type: ignore
        """Mock get within a transaction."""
        return ref_or_query.get()

    def set(self, doc_ref: Any, data: dict[str, Any], merge: Any = False) -> None:  # type: ignore
        """Mock set within a transaction."""
        doc_ref.set(data, merge=merge)

    def update(self, doc_ref: Any, data: dict[str, Any]) -> None:  # type: ignore
        """Mock update within a transaction."""
        doc_ref.update(data)

    def delete(self, doc_ref: Any) -> None:  # type: ignore
        """Mock delete within a transaction."""
        doc_ref.delete()
