"""Tests for the app factory."""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from pickaladder import create_app


class AppFirebaseTestCase(unittest.TestCase):
    """Test case for the app factory."""

    @patch("firebase_admin.initialize_app")
    @patch("firebase_admin.firestore.client")
    def test_404_error_handler(
        self, mock_firestore_client: MagicMock, mock_init_app: MagicMock
    ) -> None:
        """Test the custom 404 error handler."""
        app = create_app({"TESTING": True, "WTF_CSRF_ENABLED": False})
        with app.test_client() as client:
            response = client.get("/non_existent_page")
            self.assertEqual(response.status_code, 404)
            self.assertIn(b"Page Not Found", response.data)

    def test_mail_config_sanitization(self) -> None:
        """Test that MAIL_USERNAME and MAIL_PASSWORD are sanitized correctly."""
        env_vars = {
            "MAIL_USERNAME": '"user@example.com"',
            "MAIL_PASSWORD": '"xxxx xxxx xxxx"',  # nosec
            "SECRET_KEY": "dev",  # nosec
            "TESTING": "True",
        }
        with patch.dict(os.environ, env_vars):
            app = create_app({"TESTING": True})
            self.assertEqual(app.config["MAIL_USERNAME"], "user@example.com")
            self.assertEqual(app.config["MAIL_PASSWORD"], "xxxxxxxxxxxx")

    def test_mail_config_sanitization_single_quotes(self) -> None:
        """Test sanitization with single quotes."""
        env_vars = {
            "MAIL_USERNAME": "'user@example.com'",
            "MAIL_PASSWORD": "'xxxx xxxx xxxx'",  # nosec
            "SECRET_KEY": "dev",  # nosec
            "TESTING": "True",
        }
        with patch.dict(os.environ, env_vars):
            app = create_app({"TESTING": True})
            self.assertEqual(app.config["MAIL_USERNAME"], "user@example.com")
            self.assertEqual(app.config["MAIL_PASSWORD"], "xxxxxxxxxxxx")

    def test_mail_config_sanitization_no_quotes(self) -> None:
        """Test sanitization without quotes."""
        env_vars = {
            "MAIL_USERNAME": "user@example.com",
            "MAIL_PASSWORD": "xxxx xxxx xxxx",  # nosec
            "SECRET_KEY": "dev",  # nosec
            "TESTING": "True",
        }
        with patch.dict(os.environ, env_vars):
            app = create_app({"TESTING": True})
            self.assertEqual(app.config["MAIL_USERNAME"], "user@example.com")
            self.assertEqual(app.config["MAIL_PASSWORD"], "xxxxxxxxxxxx")

    def test_mail_config_empty_env_vars(self) -> None:
        """Test that empty environment variables fall back to default values."""
        env_vars = {
            "MAIL_SERVER": "",
            "MAIL_PORT": "",
            "MAIL_USE_TLS": "",
            "MAIL_USE_SSL": "",
            "SECRET_KEY": "dev",  # nosec
            "TESTING": "True",
        }
        with patch.dict(os.environ, env_vars):
            app = create_app({"TESTING": True})
            self.assertEqual(app.config["MAIL_SERVER"], "smtp.gmail.com")
            self.assertEqual(app.config["MAIL_PORT"], 587)
            self.assertTrue(app.config["MAIL_USE_TLS"])
            self.assertFalse(app.config["MAIL_USE_SSL"])


if __name__ == "__main__":
    unittest.main()
