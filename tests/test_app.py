"""Tests for the app factory."""
import unittest
from unittest.mock import patch

# Pre-emptive imports to ensure patch targets exist.
from pickaladder import create_app


class AppFirebaseTestCase(unittest.TestCase):
    """Test case for the app factory."""

    @patch("firebase_admin.initialize_app")
    @patch("firebase_admin.firestore.client")
    def test_404_error_handler(self, mock_firestore_client, mock_init_app):
        """Test the custom 404 error handler."""
        # This test doesn't require authentication, but we still need to mock
        # the Firebase services to prevent real initialization attempts.
        app = create_app({"TESTING": True, "WTF_CSRF_ENABLED": False})

        with app.test_client() as client:
            response = client.get("/non_existent_page")
            self.assertEqual(response.status_code, 404)
            self.assertIn(b"Page Not Found", response.data)


if __name__ == "__main__":
    unittest.main()
