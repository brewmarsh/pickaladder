import os
import importlib
import pytest
import threading
from typing import Any, Generator, List, Dict
from unittest.mock import MagicMock, patch
from werkzeug.serving import make_server
from google.cloud.firestore_v1.document import DocumentReference
from google.cloud.firestore_v1.transaction import Transaction

# --- Firestore Mocking Classes ---

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


class MockAuthService:
    """Mock for firebase_admin.auth."""

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

# --- EnhancedMockFirestore would be defined here ---
class EnhancedMockFirestore(MagicMock):
    """Placeholder for your actual EnhancedMockFirestore logic."""
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
        firebase_admin.firestore, "ArrayUnion", side_effect=lambda x: x 
    )
    p9 = patch.object(
        firebase_admin.firestore, "ArrayRemove", side_effect=lambda x: x
    )
    p10 = patch.object(firebase_admin.firestore, "FieldFilter", MagicMock)
    p11 = patch.object(
        firebase_admin.firestore, "transactional", side_effect=lambda x: x
    )

    patchers = [p1, p2, p3, p4, p5, p6, p7, p8, p9, p10, p11]
    for p in patchers:
        p.start()

    pickaladder = importlib.import_module("pickaladder")

    os.environ["FIREBASE_PROJECT_ID"] = "test-project"
    os.environ["SECRET_KEY"] = "dev"
    os.environ["MAIL_SUPPRESS_SEND"] = "True"
    os.environ["FIREBASE_API_KEY"] = "dummy_key"

    app = pickaladder.create_app({"TESTING": True, "WTF_CSRF_ENABLED": False})

    port = 5002
    server = make_server("localhost", port, app)
    t = threading.Thread(target=server.serve_forever)
    t.daemon = True
    t.start()

    yield f"http://localhost:{port}"

    server.shutdown()
    t.join()
    for p in patchers:
        p.stop()