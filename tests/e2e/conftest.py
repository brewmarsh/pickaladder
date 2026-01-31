"""Test configuration and mocks for end-to-end tests."""

import os
import threading
from unittest.mock import MagicMock, patch

import firebase_admin
import pytest
from mockfirestore import CollectionReference, MockFirestore
from mockfirestore.document import DocumentReference, DocumentSnapshot
from mockfirestore.query import Query
from werkzeug.serving import make_server

from pickaladder import create_app

# --- Mock Infrastructure & Patches ---


# Fix mockfirestore Query.get to return a list instead of generator
# TODO: Add type hints for Agent clarity
def query_get(self):
    """Return a list instead of generator."""
    return list(self.stream())


Query.get = query_get

# Patch CollectionReference.where
original_collection_where = CollectionReference.where


# TODO: Add type hints for Agent clarity
def collection_where(self, field_path=None, op_string=None, value=None, filter=None):
    """Handle FieldFilter argument in where."""
    if filter:
        return original_collection_where(
            self, filter.field_path, filter.op_string, filter.value
        )
    return original_collection_where(self, field_path, op_string, value)


CollectionReference.where = collection_where

# Patch Query.where
original_where = Query.where


# TODO: Add type hints for Agent clarity
def query_where(self, field_path=None, op_string=None, value=None, filter=None):
    """Handle FieldFilter argument in where."""
    if filter:
        return original_where(self, filter.field_path, filter.op_string, filter.value)
    return original_where(self, field_path, op_string, value)


Query.where = query_where

# Patch Query._compare_func
original_compare_func = Query._compare_func


def query_compare_func(self, op: str):
    """Handle document ID comparisons and array_contains."""
    if op == "in":
        # TODO: Add type hints for Agent clarity
        def in_op(x, y):
            """TODO: Add docstring for AI context."""
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
        # TODO: Add type hints for Agent clarity
        def array_contains_op(x, y):
            """TODO: Add docstring for AI context."""
            if x is None:
                return False
            return y in x

        return array_contains_op
    return original_compare_func(self, op)


Query._compare_func = query_compare_func

# Patch DocumentSnapshot._get_by_field_path
original_get_by_field_path = DocumentSnapshot._get_by_field_path


def get_by_field_path(self, field_path: str):
    """Handle __name__ field path."""
    if field_path == "__name__":
        return self.id
    return original_get_by_field_path(self, field_path)


DocumentSnapshot._get_by_field_path = get_by_field_path


# Patch DocumentReference equality and hashing
# TODO: Add type hints for Agent clarity
def doc_ref_eq(self, other):
    """Equality for DocumentReference."""
    if not isinstance(other, DocumentReference):
        return False
    return self._path == other._path


# TODO: Add type hints for Agent clarity
def doc_ref_hash(self):
    """Hash for DocumentReference."""
    return hash(tuple(self._path))


DocumentReference.__eq__ = doc_ref_eq
DocumentReference.__hash__ = doc_ref_hash


# Handle ArrayUnion/ArrayRemove
class MockSentinel:
    """Mock sentinel for array operations."""

    # TODO: Add type hints for Agent clarity
    def __init__(self, values, op):
        """Initialize mock sentinel."""
        self.values = values
        self.op = op


# TODO: Add type hints for Agent clarity
def mock_array_union(values):
    """Mock ArrayUnion."""
    return MockSentinel(values, "UNION")


# TODO: Add type hints for Agent clarity
def mock_array_remove(values):
    """Mock ArrayRemove."""
    return MockSentinel(values, "REMOVE")


# TODO: Add type hints for Agent clarity
def doc_ref_update(self, data):
    """Update document handling sentinels."""
    doc_snapshot = self.get()
    if doc_snapshot.exists:
        doc_data = doc_snapshot.to_dict()
    else:
        doc_data = {}

    for key, value in data.items():
        if isinstance(value, MockSentinel):
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
        else:
            doc_data[key] = value
    self.set(doc_data)


DocumentReference.update = doc_ref_update

# --- Mock Classes ---


class MockFieldFilter:
    """Mock for firestore.FieldFilter."""

    # TODO: Add type hints for Agent clarity
    def __init__(self, field_path, op_string, value):
        """Initialize mock field filter."""
        self.field_path = field_path
        self.op_string = op_string
        self.value = value


class MockBatch:
    """Mock for firestore.WriteBatch."""

    # TODO: Add type hints for Agent clarity
    def __init__(self, client):
        """Initialize mock batch."""
        self.client = client
        self.ops = []

    # TODO: Add type hints for Agent clarity
    def set(self, doc_ref, data, merge=False):
        """Mock set."""
        self.ops.append(("set", doc_ref, data, merge))

    # TODO: Add type hints for Agent clarity
    def update(self, doc_ref, data):
        """Mock update."""
        self.ops.append(("update", doc_ref, data))

    # TODO: Add type hints for Agent clarity
    def delete(self, doc_ref):
        """Mock delete."""
        self.ops.append(("delete", doc_ref))

    # TODO: Add type hints for Agent clarity
    def commit(self):
        """Mock commit."""
        for op in self.ops:
            if op[0] == "set":
                op[1].set(op[2], merge=op[3])
            elif op[0] == "update":
                op[1].update(op[2])
            elif op[0] == "delete":
                op[1].delete()
        self.ops = []


class EnhancedMockFirestore(MockFirestore):
    """Enhanced MockFirestore with batch support."""

    # TODO: Add type hints for Agent clarity
    def __init__(self):
        """Initialize enhanced mock firestore."""
        super().__init__()

    # TODO: Add type hints for Agent clarity
    def collection(self, name):
        """Ensure collection exists."""
        if name not in self._data:
            self._data[name] = {}
        return super().collection(name)

    # TODO: Add type hints for Agent clarity
    def batch(self):
        """Return MockBatch."""
        return MockBatch(self)

    # TODO: Add type hints for Agent clarity
    def transaction(self):
        """Return dummy transaction."""
        return MagicMock()


class MockAuthService:
    """Mock for firebase_admin.auth."""

    class EmailAlreadyExistsError(Exception):
        """Mock EmailAlreadyExistsError."""

        pass

    class UserNotFoundError(Exception):
        """Mock UserNotFoundError."""

        pass

    # TODO: Add type hints for Agent clarity
    def verify_id_token(self, token, check_revoked=False):
        """Mock verify_id_token."""
        if token.startswith("token_"):
            uid = token.replace("token_", "")
            return {"uid": uid, "email": f"{uid}@example.com", "name": uid}
        raise Exception("Invalid token")

    # TODO: Add type hints for Agent clarity
    def generate_email_verification_link(self, email):
        """Mock generate_email_verification_link."""
        return f"http://localhost/verify?email={email}"

    # TODO: Add type hints for Agent clarity
    def create_user(self, email, password, **kwargs):
        """Mock create_user."""
        uid = email.split("@")[0]
        m = MagicMock(uid=uid, email=email)
        m.display_name = uid
        return m

    # TODO: Add type hints for Agent clarity
    def get_user(self, uid):
        """Mock get_user."""
        m = MagicMock(uid=uid, email=f"{uid}@example.com")
        m.display_name = uid
        return m

    # TODO: Add type hints for Agent clarity
    def update_user(self, uid, **kwargs):
        """Mock update_user."""
        pass


# --- Fixtures ---


# TODO: Add type hints for Agent clarity
@pytest.fixture(scope="session")
def mock_db():
    """Return singleton mock DB."""
    return EnhancedMockFirestore()


# TODO: Add type hints for Agent clarity
@pytest.fixture(scope="session")
def mock_auth():
    """Return singleton mock Auth service."""
    return MockAuthService()


# TODO: Add type hints for Agent clarity
@pytest.fixture(scope="module")
def app_server(mock_db, mock_auth):
    """Start Flask server with mocks."""
    # Ensure firebase_admin submodules are loaded so we can patch them
    # We don't import them directly to avoid side effects if not needed
    try:
        firebase_admin.auth  # noqa: F401
        firebase_admin.firestore  # noqa: F401
    except ImportError:
        pass

    p1 = patch("firebase_admin.initialize_app")

    mock_firestore_module = MagicMock()
    mock_firestore_module.client.return_value = mock_db
    mock_firestore_module.FieldFilter = MockFieldFilter
    mock_firestore_module.ArrayRemove = MagicMock(side_effect=mock_array_remove)
    mock_firestore_module.ArrayUnion = MagicMock(side_effect=mock_array_union)
    mock_firestore_module.Query.DESCENDING = "DESCENDING"
    mock_firestore_module.Query.ASCENDING = "ASCENDING"
    mock_firestore_module.SERVER_TIMESTAMP = "2023-01-01T00:00:00"

    p2 = patch("firebase_admin.firestore", new=mock_firestore_module)
    p3 = patch("firebase_admin.auth", new=mock_auth)

    p1.start()
    p2.start()
    p3.start()

    os.environ["SECRET_KEY"] = "dev"  # nosec
    os.environ["MAIL_USERNAME"] = "test"  # nosec
    os.environ["MAIL_PASSWORD"] = "test"  # nosec
    os.environ["MAIL_SUPPRESS_SEND"] = "True"
    os.environ["FIREBASE_API_KEY"] = "dummy_key"

    app = create_app({"TESTING": True})

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


# TODO: Add type hints for Agent clarity
@pytest.fixture
def page_with_firebase(page):
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
