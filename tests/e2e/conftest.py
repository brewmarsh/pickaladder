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

# --- Mock Infrastructure & Patches ---


# Fix mockfirestore Query.get to return a list instead of generator
def query_get(self: Query) -> list[DocumentSnapshot]:
    """Return a list instead of generator."""
    return list(self.stream())


Query.get = query_get

# Patch CollectionReference.where
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

# Patch Query.where
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

# Patch Query._compare_func
original_compare_func = Query._compare_func


def query_compare_func(self: Query, op: str) -> Any:
    """Handle document ID comparisons and array_contains."""
    if op == "in":

        def in_op(x: Any, y: list[Any]) -> bool:
            """Handle 'in' operator mock."""
            normalized_y = []
            for item in y:
                if hasattr(item, "id"):
                    normalized_y.append(item.id)
                else:
                    normalized_y.append(item)
            x_val = x
            if hasattr(x, "id"):
                x_val = x.id
            return x_val in normalized_y

        return in_op
    elif op == "array_contains":

        def array_contains_op(x: list[Any] | None, y: Any) -> bool:
            """Handle 'array_contains' operator mock."""
            if x is None:
                return False
            return y in x

        return array_contains_op
    return original_compare_func(self, op)


Query._compare_func = query_compare_func

# Patch DocumentSnapshot._get_by_field_path
original_get_by_field_path = DocumentSnapshot._get_by_field_path


def get_by_field_path(self: DocumentSnapshot, field_path: str) -> Any:
    """Handle __name__ field path."""
    if field_path == "__name__":
        return self.id
    return original_get_by_field_path(self, field_path)


DocumentSnapshot._get_by_field_path = get_by_field_path

# Patch DocumentReference.get to handle transaction argument
original_get = DocumentReference.get


def doc_ref_get(self: DocumentReference, transaction: Any = None) -> DocumentSnapshot:
    """Handle transaction argument in get."""
    return original_get(self)


DocumentReference.get = doc_ref_get


# Patch DocumentReference equality and hashing
def doc_ref_eq(self: DocumentReference, other: Any) -> bool:
    """Equality for DocumentReference."""
    if not isinstance(other, DocumentReference):
        return False
    return self._path == other._path


def doc_ref_hash(self: DocumentReference) -> int:
    """Hash for DocumentReference."""
    return hash(tuple(self._path))


DocumentReference.__eq__ = doc_ref_eq
DocumentReference.__hash__ = doc_ref_hash


# Handle ArrayUnion/ArrayRemove
class MockSentinel:
    """Mock sentinel for array operations."""

    def __init__(self, values: list[Any], op: str) -> None:
        """Initialize mock sentinel."""
        self.values = values
        self.op = op

    def __iter__(self) -> Any:
        """Make sentinel iterable for logic that expects a list."""
        return iter(self.values)


def mock_array_union(values: list[Any]) -> MockSentinel:
    """Mock ArrayUnion."""
    return MockSentinel(values, "UNION")


def mock_array_remove(values: list[Any]) -> MockSentinel:
    """Mock ArrayRemove."""
    return MockSentinel(values, "REMOVE")


original_update = DocumentReference.update


def doc_ref_update(self: DocumentReference, data: dict[str, Any]) -> None:
    """Update document handling sentinels and nested fields."""
    sentinels = {k: v for k, v in data.items() if isinstance(v, MockSentinel)}
    others = {k: v for k, v in data.items() if not isinstance(v, MockSentinel)}

    if others:
        # Handle dot notation for mockfirestore manually if needed
        # but mockfirestore usually handles it.
        # We'll just use the original update and hope for the best.
        original_update(self, others)

    if sentinels:
        doc_snapshot = self.get()
        doc_data = doc_snapshot.to_dict() if doc_snapshot.exists else {}

        for key, value in sentinels.items():
            current_list = doc_data.get(key, [])
            if not isinstance(current_list, list):
                current_list = []
            if value.op == "UNION":
                for item in value.values:
                    if item not in current_list:
                        current_list.append(item)
            elif value.op == "REMOVE":
                for item in value.values:
                    if item in current_list:
                        current_list.remove(item)
            doc_data[key] = current_list
        self.set(doc_data)


DocumentReference.update = doc_ref_update

# --- Mock Classes ---


class MockFieldFilter:
    """Mock for firestore.FieldFilter."""

    def __init__(self, field_path: str, op_string: str, value: Any) -> None:
        """Initialize mock field filter."""
        self.field_path = field_path
        self.op_string = op_string
        self.value = value


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

    def __init__(self, db: EnhancedMockFirestore) -> None:
        """Initialize mock transaction."""
        super().__init__(db)
        self._read_only = False
        self._rollback = False
        self._id = "mock-transaction-id"
        self._max_attempts = 5

    def get(self, doc_ref: DocumentReference) -> DocumentSnapshot:
        """Mock get."""
        return doc_ref.get()

    def set(
        self, doc_ref: DocumentReference, data: dict[str, Any], merge: bool = False
    ) -> None:
        """Mock set."""
        doc_ref.set(data, merge=merge)

    def update(self, doc_ref: DocumentReference, data: dict[str, Any]) -> None:
        """Mock update."""
        doc_ref.update(data)

    def delete(self, doc_ref: DocumentReference) -> None:
        """Mock delete."""
        doc_ref.delete()


class EnhancedMockFirestore(MockFirestore):
    """Enhanced MockFirestore with batch and transaction support."""

    def __init__(self) -> None:
        """Initialize enhanced mock firestore."""
        super().__init__()

    def collection(self, name: str) -> CollectionReference:
        """Ensure collection exists."""
        if name not in self._data:
            self._data[name] = {}
        return super().collection(name)

    def batch(self) -> MockBatch:
        """Return MockBatch."""
        return MockBatch(self)

    def transaction(self) -> MockTransaction:
        """Return MockTransaction."""
        return MockTransaction(self)


class MockAuthService:
    """Mock for firebase_admin.auth."""

    class EmailAlreadyExistsError(Exception):
        """Mock EmailAlreadyExistsError."""

        pass

    class UserNotFoundError(Exception):
        """Mock UserNotFoundError."""

        pass

    def verify_id_token(
        self, token: str, check_revoked: bool = False
    ) -> dict[str, Any]:
        """Mock verify_id_token."""
        if token.startswith("token_"):
            uid = token.replace("token_", "")
            return {"uid": uid, "email": f"{uid}@example.com", "name": uid}
        raise Exception("Invalid token")

    def generate_email_verification_link(self, email: str) -> str:
        """Mock generate_email_verification_link."""
        return f"http://localhost/verify?email={email}"

    def create_user(self, email: str, password: str, **kwargs: Any) -> MagicMock:
        """Mock create_user."""
        uid = email.split("@", 1)[0]
        m = MagicMock(uid=uid, email=email)
        m.display_name = uid
        return m

    def get_user(self, uid: str) -> MagicMock:
        """Mock get_user."""
        m = MagicMock(uid=uid, email=f"{uid}@example.com")
        m.display_name = uid
        return m

    def update_user(self, uid: str, **kwargs: Any) -> None:
        """Mock update_user."""
        pass


# --- Fixtures ---


@pytest.fixture(scope="session")
def mock_db() -> EnhancedMockFirestore:
    """Return singleton mock DB."""
    return EnhancedMockFirestore()


@pytest.fixture(scope="session")
def mock_auth() -> MockAuthService:
    """Return singleton mock Auth service."""
    return MockAuthService()


@pytest.fixture(scope="module")
def app_server(
    mock_db: EnhancedMockFirestore, mock_auth: MockAuthService
) -> Generator[str, None, None]:
    """Start Flask server with mocks."""
    # Ensure firebase_admin submodules are loaded for patching
    importlib.import_module("firebase_admin.auth")
    importlib.import_module("firebase_admin.firestore")

    import firebase_admin.auth
    import firebase_admin.firestore
    import google.cloud.firestore

    p1 = patch("firebase_admin.initialize_app")
    p2 = patch.object(firebase_admin.firestore, "client", return_value=mock_db)
    p3 = patch.object(
        firebase_admin.auth, "create_user", side_effect=mock_auth.create_user
    )
    p4 = patch.object(
        firebase_admin.auth, "verify_id_token", side_effect=mock_auth.verify_id_token
    )
    p5 = patch.object(firebase_admin.auth, "get_user", side_effect=mock_auth.get_user)
    p6 = patch.object(
        firebase_admin.auth,
        "generate_email_verification_link",
        side_effect=mock_auth.generate_email_verification_link,
    )
    p7 = patch.object(
        firebase_admin.firestore, "SERVER_TIMESTAMP", "2023-01-01T00:00:00"
    )
    p8 = patch.object(
        firebase_admin.firestore, "ArrayUnion", side_effect=mock_array_union
    )
    p9 = patch.object(
        firebase_admin.firestore, "ArrayRemove", side_effect=mock_array_remove
    )
    p10 = patch.object(firebase_admin.firestore, "FieldFilter", MockFieldFilter)
    p11 = patch.object(
        firebase_admin.firestore, "transactional", side_effect=lambda x: x
    )
    p12 = patch.object(
        google.cloud.firestore, "transactional", side_effect=lambda x: x
    )

    # Start p1 through p12 BEFORE importing pickaladder to ensure decorators are patched
    p1.start()
    p2.start()
    p3.start()
    p4.start()
    p5.start()
    p6.start()
    p7.start()
    p8.start()
    p9.start()
    p10.start()
    p11.start()
    p12.start()

    # Move pickaladder import AFTER patching
    pickaladder = importlib.import_module("pickaladder")

    os.environ["FIREBASE_PROJECT_ID"] = "test-project"
    os.environ["SECRET_KEY"] = "dev"  # nosec
    os.environ["MAIL_USERNAME"] = "test"  # nosec
    os.environ["MAIL_PASSWORD"] = "test"  # nosec
    os.environ["MAIL_SUPPRESS_SEND"] = "True"
    os.environ["FIREBASE_API_KEY"] = "dummy_key"

    app = pickaladder.create_app({"TESTING": True})

    port = 5002
    server = make_server("localhost", port, app)
    t = threading.Thread(target=server.serve_forever)
    t.start()

    yield f"http://localhost:{port}"

    server.shutdown()
    t.join()
    p1.stop()
    p2.stop()
    p3.stop()
    p4.stop()
    p5.stop()
    p6.stop()
    p7.stop()
    p8.stop()
    p9.stop()
    p10.stop()
    p11.stop()
    p12.stop()


@pytest.fixture
def page_with_firebase(page: Any) -> Any:
    """Inject mock Firebase client into the page."""
    page.route("**/*firebase-app.js", lambda route: route.fulfill(body=""))
    page.route("**/*firebase-auth.js", lambda route: route.fulfill(body=""))

    page.add_init_script("""
        window.firebase = {
            initializeApp: function(config) {},
            auth: function() {
                return {
                    signInWithEmailAndPassword: function(email, password) {
                        return Promise.resolve({
                            user: {
                                getIdToken: function() {
                                    return Promise.resolve(
                                        "token_" + email.split('@')[0]
                                    );
                                }
                            }
                        });
                    },
                    createUserWithEmailAndPassword: function(email, password) {
                         return Promise.resolve({
                            user: {
                                getIdToken: function() {
                                    return Promise.resolve(
                                        "token_" + email.split('@')[0]
                                    );
                                }
                            }
                        });
                    },
                    onAuthStateChanged: function(callback) {
                         callback(null);
                         return function() {};
                    },
                    currentUser: null
                };
            }
        };
    """)
    return page
