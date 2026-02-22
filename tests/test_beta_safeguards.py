"""Tests for beta environment SEO safeguards."""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from pickaladder import create_app


class BetaSafeguardsTestCase(unittest.TestCase):
    """Test case for beta environment SEO safeguards."""

    @patch("firebase_admin.initialize_app")
    @patch("firebase_admin.firestore.client")
    def test_robots_tag_in_beta(
        self, mock_firestore_client: MagicMock, mock_init_app: MagicMock
    ) -> None:
        """Test that X-Robots-Tag is present when ENV is beta."""
        env_vars = {
            "FLASK_ENV": "beta",
            "SECRET_KEY": "dev",
        }
        with patch.dict(os.environ, env_vars):
            app = create_app({"TESTING": True, "WTF_CSRF_ENABLED": False})
            with app.test_client() as client:
                response = client.get("/")
                self.assertEqual(response.headers.get("X-Robots-Tag"), "noindex, nofollow")

    @patch("firebase_admin.initialize_app")
    @patch("firebase_admin.firestore.client")
    def test_robots_tag_not_in_development(
        self, mock_firestore_client: MagicMock, mock_init_app: MagicMock
    ) -> None:
        """Test that X-Robots-Tag is not present when ENV is development."""
        env_vars = {
            "FLASK_ENV": "development",
            "SECRET_KEY": "dev",
        }
        with patch.dict(os.environ, env_vars):
            app = create_app({"TESTING": True, "WTF_CSRF_ENABLED": False})
            with app.test_client() as client:
                response = client.get("/")
                self.assertIsNone(response.headers.get("X-Robots-Tag"))

    @patch("firebase_admin.initialize_app")
    @patch("firebase_admin.firestore.client")
    def test_robots_tag_not_in_production(
        self, mock_firestore_client: MagicMock, mock_init_app: MagicMock
    ) -> None:
        """Test that X-Robots-Tag is not present when ENV is production."""
        env_vars = {
            "FLASK_ENV": "production",
            "SECRET_KEY": "dev",
        }
        with patch.dict(os.environ, env_vars):
            app = create_app({"TESTING": True, "WTF_CSRF_ENABLED": False})
            with app.test_client() as client:
                response = client.get("/")
                self.assertIsNone(response.headers.get("X-Robots-Tag"))


if __name__ == "__main__":
    unittest.main()
