"""Tests for PWA integration."""

from __future__ import annotations

import unittest
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from pickaladder import create_app

if TYPE_CHECKING:
    pass


class PWATestCase(unittest.TestCase):
    """Test case for PWA integration."""

    def setUp(self) -> None:
        """Set up the test app and client."""
        self.app = create_app({"TESTING": True, "WTF_CSRF_ENABLED": False})
        self.client = self.app.test_client()

    @patch("firebase_admin.initialize_app")
    @patch("firebase_admin.firestore.client")
    def test_manifest_served(
        self, mock_firestore: MagicMock, mock_init: MagicMock
    ) -> None:
        """Test that manifest.json is served from static."""
        response = self.client.get("/static/manifest.json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/json")
        self.assertIn(b'"name": "pickaladder"', response.data)

    @patch("firebase_admin.initialize_app")
    @patch("firebase_admin.firestore.client")
    def test_service_worker_served_from_root(
        self, mock_firestore: MagicMock, mock_init: MagicMock
    ) -> None:
        """Test that service-worker.js is served from the root."""
        response = self.client.get("/service-worker.js")
        self.assertEqual(response.status_code, 200)
        # Flask might send it as application/javascript or text/javascript
        # depending on the system
        self.assertIn(response.mimetype, ["application/javascript", "text/javascript"])
        self.assertIn(b"CACHE_NAME", response.data)

    @patch("firebase_admin.initialize_app")
    @patch("firebase_admin.firestore.client")
    def test_layout_contains_pwa_elements(
        self, mock_firestore: MagicMock, mock_init: MagicMock
    ) -> None:
        """Test that layout.html contains manifest and service worker registration."""
        # We need a route that renders layout.html. auth.login usually does.
        # We might need to mock more things if auth.login does more.
        # But we can just test if the template exists and has the content if
        # we want to be safe. Or just use the test client on a simple route.

        @self.app.route("/test_layout")
        def test_layout() -> str:
            from flask import render_template

            return render_template("layout.html")

        response = self.client.get("/test_layout")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'link rel="manifest"', response.data)
        self.assertIn(b'meta name="theme-color"', response.data)
        self.assertIn(
            b"navigator.serviceWorker.register('/service-worker.js')", response.data
        )


if __name__ == "__main__":
    unittest.main()
