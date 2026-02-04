"""Tests for the tournament blueprint."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from pickaladder import create_app

# Mock user payloads
MOCK_USER_ID = "user1"
MOCK_USER_PAYLOAD = {"uid": MOCK_USER_ID, "email": "user1@example.com"}
MOCK_USER_DATA = {"name": "Tournament Owner", "isAdmin": False}


class TournamentRoutesFirebaseTestCase(unittest.TestCase):
    """Test case for the tournament blueprint."""

    def setUp(self) -> None:
        """Set up a test client and a comprehensive mock environment."""
        self.mock_firestore_service = MagicMock()

        patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            "firestore_routes": patch(
                "pickaladder.tournament.routes.firestore", new=self.mock_firestore_service
            ),
            "firestore_app": patch(
                "pickaladder.firestore", new=self.mock_firestore_service
            ),
            "verify_id_token": patch("firebase_admin.auth.verify_id_token"),
        }

        self.mocks = {name: p.start() for name, p in patchers.items()}
        for p in patchers.values():
            self.addCleanup(p.stop)

        self.app = create_app(
            {"TESTING": True, "WTF_CSRF_ENABLED": False, "SERVER_NAME": "localhost"}
        )
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self) -> None:
        """Tear down the test client."""
        self.app_context.pop()

    def _set_session_user(self) -> None:
        """Set a logged-in user in the session."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = MOCK_USER_ID
            sess["is_admin"] = False
        self.mocks["verify_id_token"].return_value = MOCK_USER_PAYLOAD

    def _get_auth_headers(self) -> dict[str, str]:
        """Get standard authentication headers for tests."""
        return {"Authorization": "Bearer mock-token"}

    def test_create_tournament(self) -> None:
        """Test successfully creating a new tournament."""
        self._set_session_user()
        mock_db = self.mock_firestore_service.client.return_value

        # Mock user fetch for before_request
        mock_user_doc = mock_db.collection("users").document(MOCK_USER_ID)
        mock_user_snapshot = MagicMock()
        mock_user_snapshot.exists = True
        mock_user_snapshot.to_dict.return_value = MOCK_USER_DATA
        mock_user_doc.get.return_value = mock_user_snapshot

        mock_tournaments_collection = mock_db.collection("tournaments")
        mock_doc_ref = MagicMock()
        mock_doc_ref.id = "new_tournament_id"
        mock_tournaments_collection.add.return_value = (None, mock_doc_ref)

        # Mock the document fetch for the redirect
        mock_tournament_doc = mock_tournaments_collection.document.return_value
        mock_tournament_snapshot = MagicMock()
        mock_tournament_snapshot.exists = True
        mock_tournament_snapshot.to_dict.return_value = {
            "name": "Summer Open",
            "date": "2024-06-01",
            "location": "Courtside",
            "matchType": "singles",
            "ownerRef": mock_user_doc,
            "participants": []
        }
        mock_tournament_doc.get.return_value = mock_tournament_snapshot

        # Mock UserService.get_user_friends
        with patch("pickaladder.tournament.routes.UserService.get_user_friends") as mock_friends:
            mock_friends.return_value = []

            response = self.client.post(
                "/tournaments/create",
                headers=self._get_auth_headers(),
                data={
                    "name": "Summer Open",
                    "date": "2024-06-01",
                    "location": "Courtside",
                    "match_type": "singles"
                },
                follow_redirects=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Tournament created successfully.", response.data)
        mock_tournaments_collection.add.assert_called_once()
        call_args = mock_tournaments_collection.add.call_args[0]
        self.assertEqual(call_args[0]["name"], "Summer Open")
        self.assertEqual(call_args[0]["matchType"], "singles")

    def test_list_tournaments(self) -> None:
        """Test listing tournaments."""
        self._set_session_user()
        mock_db = self.mock_firestore_service.client.return_value

        # Mock user fetch for before_request
        mock_user_doc = mock_db.collection("users").document(MOCK_USER_ID)
        mock_user_snapshot = MagicMock()
        mock_user_snapshot.exists = True
        mock_user_snapshot.to_dict.return_value = MOCK_USER_DATA
        mock_user_doc.get.return_value = mock_user_snapshot

        mock_query = mock_db.collection.return_value.where.return_value
        mock_query.stream.return_value = [] # Empty list for simplicity

        response = self.client.get(
            "/tournaments/",
            headers=self._get_auth_headers(),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Tournaments", response.data)


if __name__ == "__main__":
    unittest.main()
