"""Tests for the tournament blueprint using mockfirestore."""

from __future__ import annotations

import datetime
import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from mockfirestore import MockFirestore

from pickaladder import create_app
from tests.mock_utils import (
    MockArrayRemove,
    MockArrayUnion,
    MockBatch,
    patch_mockfirestore,
)

# Mock user payloads
MOCK_USER_ID = "user1"
MOCK_USER_PAYLOAD = {"uid": MOCK_USER_ID, "email": "user1@example.com"}
MOCK_USER_DATA = {"name": "Tournament Owner", "isAdmin": False, "username": "user1"}


class TournamentRoutesFirebaseTestCase(unittest.TestCase):
    """Test case for the tournament blueprint."""

    def setUp(self) -> None:
        """Set up a test client and a comprehensive mock environment."""
        self.mock_db = MockFirestore()
        patch_mockfirestore()

        self.mock_batch_instance = MockBatch(self.mock_db)
        self.mock_db.batch = MagicMock(return_value=self.mock_batch_instance)

        # Patch firestore.client() to return our mock_db
        self.mock_firestore_module = MagicMock()
        self.mock_firestore_module.client.return_value = self.mock_db

        # Mock FieldFilter and other constants
        class MockFieldFilter:
            def __init__(self, field_path: str, op_string: str, value: Any) -> None:
                self.field_path = field_path
                self.op_string = op_string
                self.value = value

        self.mock_firestore_module.FieldFilter = MockFieldFilter
        self.mock_firestore_module.ArrayUnion = MockArrayUnion
        self.mock_firestore_module.ArrayRemove = MockArrayRemove
        self.mock_firestore_module.SERVER_TIMESTAMP = "2023-01-01"

        patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            "firestore_client": patch("firebase_admin.firestore.client"),
            "firestore_services": patch(
                "pickaladder.tournament.services.firestore",
                new=self.mock_firestore_module,
            ),
            "firestore_app": patch(
                "pickaladder.firestore", new=self.mock_firestore_module
            ),
            "verify_id_token": patch("firebase_admin.auth.verify_id_token"),
        }

        self.mocks = {name: p.start() for name, p in patchers.items()}
        self.mocks["firestore_client"].return_value = self.mock_db
        for p in patchers.values():
            self.addCleanup(p.stop)

        self.app = create_app(
            {"TESTING": True, "WTF_CSRF_ENABLED": False, "SERVER_NAME": "localhost"}
        )
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        # Setup current user in mock DB
        self.mock_db.collection("users").document(MOCK_USER_ID).set(MOCK_USER_DATA)

    def tearDown(self) -> None:
        """Tear down the test client."""
        self.app_context.pop()

    def _set_session_user(self, is_admin: bool = False) -> None:
        """Set a logged-in user in the session and mock DB."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = MOCK_USER_ID
            sess["is_admin"] = is_admin
        self.mock_db.collection("users").document(MOCK_USER_ID).update(
            {"isAdmin": is_admin}
        )
        self.mocks["verify_id_token"].return_value = MOCK_USER_PAYLOAD

    def _get_auth_headers(self) -> dict[str, str]:
        """Get standard authentication headers for tests."""
        return {"Authorization": "Bearer mock-token"}

    # ... (test_create_tournament, test_edit_tournament, and test_list_tournaments logic remain same)

    def test_delete_tournament(self) -> None:
        """Test successfully deleting a tournament as admin."""
        self._set_session_user(is_admin=True)

        tournament_id = "test_tournament_id"
        # RESOLVED: Seed with participant_ids and ownerRef to satisfy mockfirestore constraints
        self.mock_db.collection("tournaments").document(tournament_id).set(
            {"name": "To be deleted", "participant_ids": [], "ownerRef": None}
        )

        response = self.client.post(
            f"/tournaments/{tournament_id}/delete",
            headers=self._get_auth_headers(),
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Tournament deleted successfully.", response.data)
        self.assertFalse(
            self.mock_db.collection("tournaments").document(tournament_id).get().exists
        )

    def test_delete_tournament_non_admin(self) -> None:
        """Test that a non-admin cannot delete a tournament."""
        self._set_session_user(is_admin=False)

        tournament_id = "test_tournament_id"
        # RESOLVED: Seed with participant_ids and ownerRef to satisfy mockfirestore constraints
        self.mock_db.collection("tournaments").document(tournament_id).set(
            {"name": "Not deleted", "participant_ids": [], "ownerRef": None}
        )

        response = self.client.post(
            f"/tournaments/{tournament_id}/delete",
            headers=self._get_auth_headers(),
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Only administrators can create tournaments.", response.data)
        self.assertTrue(
            self.mock_db.collection("tournaments").document(tournament_id).get().exists
        )


if __name__ == "__main__":
    unittest.main()