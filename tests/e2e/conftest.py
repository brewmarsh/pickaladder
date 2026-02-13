class MockTransaction(Transaction):
    """Mock for firestore.Transaction."""

    def __init__(self, db: Any) -> None:
        """Initialize mock transaction."""
        # Note: We don't call super().__init__ because it requires a live client
        self.db = db
        self._read_only = False
        self._id = "mock-transaction-id"
        self._max_attempts = 5

    def _begin(self, retry_id: Any = None) -> None:
        """Mock begin."""
        pass

    def _rollback(self) -> None:
        """Mock rollback method to prevent TypeError in library calls."""
        pass

    def _clean_up(self) -> None:
        """Mock clean up."""
        pass

    def _commit(self) -> list[Any]:
        """Mock commit."""
        return []

    def get(self, ref_or_query: Any) -> Any:
        """Mock get within a transaction."""
        return ref_or_query.get()

    def set(self, doc_ref: Any, data: Dict[str, Any], merge: bool = False) -> None:
        """Mock set within a transaction."""
        doc_ref.set(data, merge=merge)

    def update(self, doc_ref: Any, data: Dict[str, Any]) -> None:
        """Mock update within a transaction."""
        doc_ref.update(data)

    def delete(self, doc_ref: Any) -> None:
        """Mock delete within a transaction."""
        doc_ref.delete()