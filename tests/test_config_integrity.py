"""Test to ensure configuration integrity, specifically for Firebase mocking."""

import unittest.mock

import firebase_admin
from mockfirestore import MockFirestore

from pickaladder import create_app


def test_app_initializes_db_client_in_test_mode() -> None:
    """
    Test that the app correctly initializes the Firestore client in test mode.
    It should return a Mock object instead of raising a ValueError.
    """
    app = create_app({"TESTING": True})
    with app.app_context():
        # Explicitly call firestore.client()
        # If the app is misconfigured for testing, this will raise a ValueError.
        client = firebase_admin.firestore.client()

        # Assert: It should not be a ValueError (implicitly handled if it reaches here)
        # Assert: It should return a Mock object or a MockFirestore object.
        assert isinstance(
            client, (unittest.mock.Mock, unittest.mock.MagicMock, MockFirestore)
        )
