import unittest
from unittest.mock import patch, MagicMock
import re

# Pre-emptive imports to ensure patch targets exist.

from pickaladder import create_app

# Mock user payloads
MOCK_USER_ID = "user1"
MOCK_USER_PAYLOAD = {"uid": MOCK_USER_ID, "email": "user1@example.com"}
MOCK_USER_DATA = {"name": "Test User", "isAdmin": False}
MOCK_PASSWORD = "Password123"  # nosec


class AuthFirebaseTestCase(unittest.TestCase):
    def setUp(self):
        """Set up a test client and a comprehensive mock environment."""
        self.mock_auth_service = MagicMock()
        self.mock_firestore_service = MagicMock()

        patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            "auth_routes_auth": patch(
                "pickaladder.auth.routes.auth", new=self.mock_auth_service
            ),
            "auth_routes_firestore": patch(
                "pickaladder.auth.routes.firestore", new=self.mock_firestore_service
            ),
        }

        self.mocks = {name: p.start() for name, p in patchers.items()}
        for p in patchers.values():
            self.addCleanup(p.stop)

        self.app = create_app({"TESTING": True, "SERVER_NAME": "localhost"})
        self.client = self.app.test_client()

    @patch("pickaladder.auth.routes.send_email")
    def test_successful_registration(self, mock_send_email):
        """Test user registration with valid data."""
        # Mock the username check to return an empty list, simulating username is available.
        mock_db = self.mock_firestore_service.client.return_value
        mock_users_collection = mock_db.collection("users")
        mock_users_collection.where.return_value.limit.return_value.get.return_value = []

        # Mock the return value of create_user
        self.mock_auth_service.create_user.return_value = MagicMock(uid="new_user_uid")

        # First, get the register page to get a valid CSRF token
        register_page_response = self.client.get("/auth/register")
        csrf_token_match = re.search(
            r'<input id="csrf_token" name="csrf_token" type="hidden" value="([^"]+)">',
            register_page_response.data.decode(),
        )
        self.assertIsNotNone(csrf_token_match)
        csrf_token = csrf_token_match.group(1)

        response = self.client.post(
            "/auth/register",
            data={
                "csrf_token": csrf_token,
                "username": "newuser",
                "email": "new@example.com",
                "password": MOCK_PASSWORD,
                "confirm_password": MOCK_PASSWORD,
                "name": "New User",
                "dupr_rating": 4.5,
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Registration successful!", response.data)
        self.mock_auth_service.create_user.assert_called_once()
        self.mock_firestore_service.client.return_value.collection("users").document(
            "new_user_uid"
        ).set.assert_called_once()
        mock_send_email.assert_called_once()

    def test_login_page_loads(self):
        """Test that the login page loads correctly."""
        # Mock the admin check to prevent a redirect to /install.
        mock_db = self.mock_firestore_service.client.return_value
        mock_db.collection(
            "users"
        ).where.return_value.limit.return_value.get.return_value = [MagicMock()]

        response = self.client.get("/auth/login")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Login", response.data)

    def test_session_login(self):
        """Test the session login endpoint."""
        # Mock the return value of verify_id_token
        self.mock_auth_service.verify_id_token.return_value = MOCK_USER_PAYLOAD

        # Mock the Firestore document
        mock_db = self.mock_firestore_service.client.return_value
        mock_users_collection = mock_db.collection("users")
        mock_user_doc = mock_users_collection.document(MOCK_USER_ID)
        mock_doc_snapshot = MagicMock()
        mock_doc_snapshot.exists = True
        mock_doc_snapshot.to_dict.return_value = MOCK_USER_DATA
        mock_user_doc.get.return_value = mock_doc_snapshot

        # First, get the login page to get a valid CSRF token
        login_page_response = self.client.get("/auth/login")
        csrf_token_match = re.search(
            r'name="csrf-token" content="([^"]+)"', login_page_response.data.decode()
        )
        self.assertIsNotNone(csrf_token_match)
        csrf_token = csrf_token_match.group(1)

        response = self.client.post(
            "/auth/session_login",
            json={"idToken": "test_token"},
            headers={"X-CSRFToken": csrf_token},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"status": "success"})
        with self.client.session_transaction() as sess:
            self.assertEqual(sess["user_id"], MOCK_USER_ID)
            self.assertEqual(sess["is_admin"], False)

    def test_install_admin_user(self):
        """Test the creation of the initial admin user."""
        # Mock the admin check to simulate no admin user exists.
        mock_db = self.mock_firestore_service.client.return_value
        mock_users_collection = mock_db.collection("users")
        mock_users_collection.where.return_value.limit.return_value.get.return_value = []

        # Mock the return value of create_user
        self.mock_auth_service.create_user.return_value = MagicMock(
            uid="admin_user_uid"
        )

        # More specific mocking for document calls
        mock_user_doc = MagicMock()
        mock_settings_doc = MagicMock()

        def document_side_effect(doc_id):
            if doc_id == "admin_user_uid":
                return mock_user_doc
            elif doc_id == "enforceEmailVerification":
                return mock_settings_doc
            return MagicMock()

        self.mock_firestore_service.client.return_value.collection.return_value.document.side_effect = document_side_effect

        # First, get the install page to get a valid CSRF token
        install_page_response = self.client.get("/auth/install")
        csrf_token_match = re.search(
            r'name="csrf_token" value="([^"]+)"', install_page_response.data.decode()
        )
        self.assertIsNotNone(csrf_token_match)
        csrf_token = csrf_token_match.group(1)

        response = self.client.post(
            "/auth/install",
            data={
                "csrf_token": csrf_token,
                "username": "admin",
                "email": "admin@example.com",
                "password": MOCK_PASSWORD,
                "name": "Admin User",
                "dupr_rating": 5.0,
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Admin user created successfully.", response.data)
        self.mock_auth_service.create_user.assert_called_once_with(
            email="admin@example.com",
            password=MOCK_PASSWORD,
            email_verified=True,
        )
        mock_user_doc.set.assert_called_once()
        mock_settings_doc.set.assert_called_once_with({"value": True})

    @patch("pickaladder.auth.routes.send_email")
    def test_registration_with_invite_token(self, mock_send_email):
        """Test user registration with a valid invite token."""
        # Mock the username check to return an empty list, simulating username is available.
        mock_db = self.mock_firestore_service.client.return_value
        mock_users_collection = mock_db.collection("users")
        mock_users_collection.where.return_value.limit.return_value.get.return_value = []

        # Mock the invite token
        mock_invite_doc = MagicMock()
        mock_invite_doc.exists = True
        mock_invite_doc.to_dict.return_value = {"userId": "inviter_uid", "used": False}
        mock_db.collection(
            "invites"
        ).document.return_value.get.return_value = mock_invite_doc

        # Mock the return value of create_user
        self.mock_auth_service.create_user.return_value = MagicMock(uid="new_user_uid")

        # First, get the register page to get a valid CSRF token and set the invite token in the session
        with self.client.session_transaction() as sess:
            sess["invite_token"] = "test_invite_token"
        register_page_response = self.client.get(
            "/auth/register?invite_token=test_invite_token"
        )
        csrf_token_match = re.search(
            r'<input id="csrf_token" name="csrf_token" type="hidden" value="([^"]+)">',
            register_page_response.data.decode(),
        )
        self.assertIsNotNone(csrf_token_match)
        csrf_token = csrf_token_match.group(1)

        response = self.client.post(
            "/auth/register",
            data={
                "csrf_token": csrf_token,
                "username": "newuser",
                "email": "new@example.com",
                "password": MOCK_PASSWORD,
                "confirm_password": MOCK_PASSWORD,
                "name": "New User",
                "dupr_rating": 4.5,
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Registration successful!", response.data)

        # Check that the friendship was created
        mock_db.batch.assert_called_once()
        mock_db.collection("invites").document(
            "test_invite_token"
        ).update.assert_called_once_with({"used": True})


if __name__ == "__main__":
    unittest.main()
