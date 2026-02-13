import os
import importlib
import pytest
import threading
from typing import Any, Generator, List, Dict, TYPE_CHECKING
from unittest.mock import MagicMock, patch
from mockfirestore import CollectionReference, MockFirestore, Transaction
from mockfirestore.document import DocumentReference, DocumentSnapshot
from mockfirestore.query import Query
from werkzeug.serving import make_server

if TYPE_CHECKING:
    from collections.abc import Generator

# --- Mock Infrastructure & Patches ---

# Fix mockfirestore Query.get to return a list instead of generator
def query_get(self: Query) -> list[DocumentSnapshot]:
    """Return a list instead of generator."""
    return list(self.stream())

Query.get = query_get

# Patch CollectionReference.where to handle FieldFilter
original_collection_where = CollectionReference.where

def collection_where(
    self: CollectionReference,
    field_path: str | None = None,
    op_string: str | None = None,
    value: Any = None,
    filter: Any = None,
) -> Query:
    """Handle FieldFilter argument in where."""
    if filter:
        return original_collection_where(
            self, filter.field_path, filter.op_string, filter.value
        )
    return original_collection_where(self, field_path, op_string, value)

CollectionReference.where = collection_where

# Patch Query.where to handle FieldFilter
original_where = Query.where

def query_where(
    self: Query,
    field_path: str | None = None,
    op_string: str | None = None,
    value: Any = None,
    filter: Any = None,
) -> Query:
    """Handle FieldFilter argument in where."""
    if filter:
        return original_where(self, filter.field_path, filter.op_string, filter.value)
    return original_where(self, field_path, op_string, value)

Query.where = query_where

# Patch Query._compare_func for advanced operators
original_compare_func = Query._compare_func

def query_compare_func(self: Query, op: str) -> Any:
    """Handle document ID comparisons and array_contains."""
    if op == "in":
        def in_op(x: Any, y: list[Any]) -> bool:
            normalized_y = [item.id if hasattr(item, "id") else item for item in y]
            x_val = x.id if hasattr(x, "id") else x
            return x_val in normalized_y
        return in_op
    elif op == "array_contains":
        def array_contains_op(x: list[Any] | None, y: Any) -> bool:
            return y in x if x is not None else False
        return array_contains_op
    return original_compare_func(self, op)

Query._compare_func = query_compare_func

# Patch DocumentSnapshot for path handling
original_get_by_field_path = DocumentSnapshot._get_by_field_path

def get_by_field_path(self: DocumentSnapshot, field_path: str) -> Any:
    """Handle __name__ field path."""
    if field_path == "__name__":
        return self.id
    return original_get_by_field_path(self, field_path)

DocumentSnapshot._get_by_field_path = get_by_field_path

# Patch DocumentReference for transaction and equality
original_get = DocumentReference.get
DocumentReference.get = lambda self, transaction=None: original_get(self)
DocumentReference.__eq__ = lambda self, other: isinstance(other, DocumentReference) and self._path == other._path
DocumentReference.__hash__ = lambda self: hash(tuple(self._path))

# --- Mock Sentinel Support ---

class MockSentinel:
    """Mock sentinel for array operations."""
    def __init__(self, values: list[Any], op: str) -> None:
        self.values = values
        self.op = op
    def __iter__(self) -> Any:
        return iter(self.values)

def mock_array_union(values: list[Any]) -> MockSentinel:
    return MockSentinel(values, "UNION")

def mock_array_remove(values: list[Any]) -> MockSentinel:
    return MockSentinel(values, "REMOVE")

original_update = DocumentReference.update

def doc_ref_update(self: DocumentReference, data: dict[str, Any]) -> None:
    """Update document handling sentinels and nested fields."""
    sentinels = {k: v for k, v in data.items() if isinstance(v, MockSentinel)}
    others = {k: v for k, v in data.items() if not isinstance(v, MockSentinel)}
    if others:
        original_update(self, others)
    if sentinels:
        doc_snapshot = self.get()
        doc_data = doc_snapshot.to_dict() if doc_snapshot.exists else {}
        for key, value in sentinels.items():
            current_list = doc_data.get(key, [])
            if not isinstance(current_list, list): current_list = []
            if value.op == "UNION":
                for item in value.values:
                    if item not in current_list: current_list.append(item)
            elif value.op == "REMOVE":
                for item in value.values:
                    if item in current_list: current_list.remove(item)
            doc_data[key] = current_list
        self.set(doc_data)

DocumentReference.update = doc_ref_update

# --- Mock Classes ---

class MockFieldFilter:
    """Mock for firestore.FieldFilter."""
    def __init__(self, field_path: str, op_string: str, value: Any) -> None:
        self.field_path = field_path
        self.op_string = op_string
        self.value = value

class MockTransaction(Transaction):
    """Mock for firestore.Transaction."""
    def __init__(self, db: Any) -> None:
        super().__init__(db)
        self.db = db
        self._read_only = False
        self._rollback_called = False
        self._id = "mock-transaction-id"
        self._max_attempts = 5

    def _rollback(self) -> None:
        """Mock rollback."""
        self._rollback_called = True

    def get(self, ref_or_query: Any) -> Any:
        return ref_or_query.get()

    def set(self, doc_ref: Any, data: Dict[str, Any], merge: bool = False) -> None:
        doc_ref.set(data, merge=merge)

    def update(self, doc_ref: Any, data: Dict[str, Any]) -> None:
        doc_ref.update(data)

    def delete(self, doc_ref: Any) -> None:
        doc_ref.delete()

# --- Fixtures ---

class EnhancedMockFirestore(MockFirestore):
    """Enhanced mock Firestore with custom transaction support."""
    def transaction(self, **kwargs) -> MockTransaction:
        return MockTransaction(self)

@pytest.fixture(scope="session")
def mock_db() -> EnhancedMockFirestore:
    return EnhancedMockFirestore()

@pytest.fixture(scope="module")
def app_server(mock_db: EnhancedMockFirestore) -> Generator[str, None, None]:
    """Start Flask server with mocks."""
    importlib.import_module("firebase_admin.auth")
    importlib.import_module("firebase_admin.firestore")
    import firebase_admin.auth
    import firebase_admin.firestore

    p1 = patch("firebase_admin.initialize_app")
    p2 = patch.object(firebase_admin.firestore, "client", return_value=mock_db)
    
    # Start patches
    p1.start()
    p2.start()

    pickaladder = importlib.import_module("pickaladder")
    os.environ["FIREBASE_PROJECT_ID"] = "test-project"
    app = pickaladder.create_app({"TESTING": True, "WTF_CSRF_ENABLED": False})

    port = 5002
    server = make_server("localhost", port, app)
    t = threading.Thread(target=server.serve_forever)
    t.daemon = True
    t.start()

    yield f"http://localhost:{port}"

    server.shutdown()
    t.join()
    p1.stop()
    p2.stop()