"""Tests for the health endpoint."""

import unittest
from unittest.mock import MagicMock, patch

from pickaladder import create_app


class HealthTestCase(unittest.TestCase):
    """Test case for the health endpoint."""

    @patch("firebase_admin.initialize_app")
    @patch("firebase_admin.firestore.client")
    def test_health_endpoint(
        self, mock_firestore_client: MagicMock, mock_init_app: MagicMock
    ) -> None:
        """Test that the /health endpoint returns 200 OK and status healthy."""
        app = create_app({"TESTING": True, "WTF_CSRF_ENABLED": False})
        with app.test_client() as client:
            response = client.get("/health")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json(), {"status": "healthy"})


if __name__ == "__main__":
    unittest.main()
