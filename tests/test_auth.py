import unittest
from unittest.mock import patch, MagicMock

# Pre-emptive imports to ensure patch targets exist.

from pickaladder import create_app

# Mock user payloads
MOCK_USER_ID = "user1"
MOCK_USER_PAYLOAD = {"uid": MOCK_USER_ID, "email": "user1@example.com"}
MOCK_USER_DATA = {"name": "Test User", "isAdmin": False}


class AuthFirebaseTestCase(unittest.TestCase):

    def setUp(self):
        """Set up a test client and a comprehensive mock environment."""
        self.mock_auth_service = MagicMock()
        self.mock_firestore_service = MagicMock()

        patchers = {
            'init_app': patch('firebase_admin.initialize_app'),
            # Patch for the `before_request` user loader in `__init__.py`.
            'init_firebase_admin': patch('pickaladder.firebase_admin'),
            'init_firestore': patch('pickaladder.firestore', new=self.mock_firestore_service),
            # Patch for the auth routes.
            'auth_routes_auth': patch('pickaladder.auth.routes.auth', new=self.mock_auth_service),
            'auth_routes_firestore': patch('pickaladder.auth.routes.firestore', new=self.mock_firestore_service),
        }

        self.mocks = {name: p.start() for name, p in patchers.items()}
        for p in patchers.values():
            self.addCleanup(p.stop)

        self.mocks['init_firebase_admin'].auth = self.mock_auth_service

        self.app = create_app({
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SERVER_NAME": "localhost"
        })
        self.client = self.app.test_client()

    def test_successful_registration(self):
        """Test user registration with valid data."""
        # Mock the username check to return an empty list, simulating username is available.
        mock_db = self.mock_firestore_service.client.return_value
        mock_users_collection = mock_db.collection('users')
        mock_users_collection.where.return_value.limit.return_value.get.return_value = []

        # Mock the return value of create_user
        self.mock_auth_service.create_user.return_value = MagicMock(uid="new_user_uid")

        response = self.client.post(
            "/auth/register",
            data={
                "username": "newuser",
                "email": "new@example.com",
                "password": "Password123",
                "confirm_password": "Password123",
                "name": "New User",
                "dupr_rating": 4.5,
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Registration successful!", response.data)
        self.mock_auth_service.create_user.assert_called_once()
        self.mock_firestore_service.client.return_value.collection('users').document('new_user_uid').set.assert_called_once()

    def test_login_page_loads(self):
        """Test that the login page loads correctly."""
        # Mock the admin check to prevent a redirect to /install.
        mock_db = self.mock_firestore_service.client.return_value
        mock_db.collection('users').where.return_value.limit.return_value.get.return_value = [MagicMock()]

        response = self.client.get("/auth/login")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Login", response.data)


if __name__ == "__main__":
    unittest.main()