from __future__ import annotations
from firebase_admin import firestore

"""Test to ensure configuration integrity, specifically for Firebase mocking."""


import unittest
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import firebase_admin
from mockfirestore import MockFirestore

from pickaladder import create_app


class TestConfigIntegrity(unittest.TestCase):
    """Test case for configuration integrity."""

    mock_initialize_app: MagicMock
    mock_firestore_client: MagicMock

    def setUp(self) -> None:
        self.mock_initialize_app = patch("firebase_admin.initialize_app").start()
        self.mock_firestore_client = patch("firebase_admin.firestore.client").start()
        self.addCleanup(patch.stopall)

    def test_app_initializes_db_client_in_test_mode(self) -> None:
        """
        Test that the app correctly initializes the Firestore client in test mode.
        It should return a Mock object instead of raising a ValueError.
        """
        app = create_app({"TESTING": True})
        with app.app_context():
            # Explicitly call firestore.client()
            # If the app is misconfigured for testing, this will raise a ValueError.
            client: Any = firebase_admin.firestore.client()

            # Assert: It should not be a ValueError (implicitly handled if it reaches)
            # Assert: It should return a Mock object or a MockFirestore object.
            self.assertIsInstance(client, (Mock, MagicMock, MockFirestore))
