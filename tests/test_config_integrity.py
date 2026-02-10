"""Test to ensure configuration integrity, specifically for Firebase mocking."""

import unittest
from unittest.mock import MagicMock, Mock

import firebase_admin
from mockfirestore import MockFirestore

from pickaladder import create_app


class TestConfigIntegrity(unittest.TestCase):
    """Test case for configuration integrity."""

    def test_app_initializes_db_client_in_test_mode(self) -> None:
        """
        Test that the app correctly initializes the Firestore client in test mode.
        It should return a Mock object instead of raising a ValueError.
        """
        app = create_app({"TESTING": True})
        with app.app_context():
            # Explicitly call firestore.client()
            # If the app is misconfigured for testing, this will raise a ValueError.
            client = firebase_admin.firestore.client()

            # Assert: It should not be a ValueError (implicitly handled if it reaches)
            # Assert: It should return a Mock object or a MockFirestore object.
            self.assertIsInstance(client, (Mock, MagicMock, MockFirestore))
