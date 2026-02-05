"""Tests for tournament invite functionality."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from pickaladder import create_app
from pickaladder.user.services import UserService

# Mock user payloads
MOCK_USER_ID = "user1"
MOCK_USER_PAYLOAD = {"uid": MOCK_USER_ID, "email": "user1@example.com"}
MOCK_USER_DATA = {"username": "user1", "name": "User One", "isAdmin": False}


class TournamentInvitesTestCase(unittest.TestCase):
    """Test case for tournament invites."""

    def setUp(self) -> None:
        """Set up a test client and a comprehensive mock environment."""
        self.mock_firestore_service = MagicMock()

        patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            "firestore_routes": patch(
                "pickaladder.tournament.routes.firestore",
                new=self.mock_firestore_service,
            ),
            "firestore_services": patch(
                "pickaladder.tournament.services.firestore",
                new=self.mock_firestore_service,
            ),
            "firestore_user_routes": patch(
                "pickaladder.user.routes.firestore",
                new=self.mock_firestore_service,
            ),
            "firestore_user_utils": patch(
                "pickaladder.user.services.firestore",
                new=self.mock_firestore_service,
            ),
            "firestore_app": patch(
                "pickaladder.firestore", new=self.mock_firestore_service
            ),
            "firestore_init": patch(
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

    def test_get_pending_tournament_invites(self) -> None:
        """Test UserService.get_pending_tournament_invites."""
        mock_db = self.mock_firestore_service.client.return_value

        # Mock tournament docs
        mock_doc1 = MagicMock()
        mock_doc1.id = "t1"
        mock_user_ref = MagicMock()
        mock_user_ref.id = MOCK_USER_ID
        mock_doc1.to_dict.return_value = {
            "name": "Tournament 1",
            "participants": [{"userRef": mock_user_ref, "status": "pending"}],
        }

        mock_doc2 = MagicMock()
        mock_doc2.id = "t2"
        mock_doc2.to_dict.return_value = {
            "name": "Tournament 2",
            "participants": [{"userRef": mock_user_ref, "status": "accepted"}],
        }

        mock_query = mock_db.collection.return_value.where.return_value
        mock_query.stream.return_value = [mock_doc1, mock_doc2]

        invites = UserService.get_pending_tournament_invites(mock_db, MOCK_USER_ID)

        self.assertEqual(len(invites), 1)
        self.assertEqual(invites[0]["id"], "t1")
        self.assertEqual(invites[0]["name"], "Tournament 1")

    def test_accept_invite_route(self) -> None:
        """Test POST /tournaments/<id>/accept."""
        self._set_session_user()
        mock_db = self.mock_firestore_service.client.return_value

        # Mock user fetch for before_request
        mock_user_doc = mock_db.collection("users").document(MOCK_USER_ID)
        mock_user_doc.id = MOCK_USER_ID
        mock_user_snapshot = MagicMock()
        mock_user_snapshot.exists = True
        mock_user_snapshot.to_dict.return_value = MOCK_USER_DATA
        mock_user_doc.get.return_value = mock_user_snapshot

        tournament_id = "test_t"
        mock_tournament_ref = mock_db.collection("tournaments").document(tournament_id)

        # Mock transaction
        mock_transaction = MagicMock()
        mock_db.transaction.return_value = mock_transaction

        mock_snapshot = MagicMock()
        mock_snapshot.exists = True
        mock_user_ref = MagicMock()
        mock_user_ref.id = MOCK_USER_ID
        mock_snapshot.get.side_effect = lambda key: {
            "participants": [{"userRef": mock_user_ref, "status": "pending"}]
        }[key]
        mock_tournament_ref.get.return_value = mock_snapshot

        # We need to simulate the transactional behavior.
        # The route calls update_in_transaction(db.transaction(), tournament_ref)
        # In the route:
        # success = update_in_transaction(db.transaction(), tournament_ref)

        # Since we are mocking the transaction object, we need to make sure
        # the transaction decorator/wrapper works.
        # But wait, the route uses @firestore.transactional which we might
        # need to patch if it doesn't work well with MagicMocks.

        with patch(
            "pickaladder.tournament.routes.firestore.transactional"
        ) as mock_trans_decorator:
            # Make the decorator just return the function
            mock_trans_decorator.side_effect = lambda x: x

            response = self.client.post(
                f"/tournaments/{tournament_id}/accept",
                headers=self._get_auth_headers(),
                follow_redirects=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"You have accepted the tournament invite!", response.data)

    def test_decline_invite_route(self) -> None:
        """Test POST /tournaments/<id>/decline."""
        self._set_session_user()
        mock_db = self.mock_firestore_service.client.return_value

        # Mock user fetch for before_request
        mock_user_doc = mock_db.collection("users").document(MOCK_USER_ID)
        mock_user_doc.id = MOCK_USER_ID
        mock_user_snapshot = MagicMock()
        mock_user_snapshot.exists = True
        mock_user_snapshot.to_dict.return_value = MOCK_USER_DATA
        mock_user_doc.get.return_value = mock_user_snapshot

        tournament_id = "test_t"
        mock_tournament_ref = mock_db.collection("tournaments").document(tournament_id)

        # Mock transaction
        mock_transaction = MagicMock()
        mock_db.transaction.return_value = mock_transaction

        mock_snapshot = MagicMock()
        mock_snapshot.exists = True
        mock_user_ref = MagicMock()
        mock_user_ref.id = MOCK_USER_ID
        mock_snapshot.get.side_effect = lambda key: {
            "participants": [{"userRef": mock_user_ref, "status": "pending"}],
            "participant_ids": [MOCK_USER_ID],
        }[key]
        mock_tournament_ref.get.return_value = mock_snapshot

        with patch(
            "pickaladder.tournament.routes.firestore.transactional"
        ) as mock_trans_decorator:
            mock_trans_decorator.side_effect = lambda x: x

            response = self.client.post(
                f"/tournaments/{tournament_id}/decline",
                headers=self._get_auth_headers(),
                follow_redirects=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"You have declined the tournament invite.", response.data)


if __name__ == "__main__":
    unittest.main()
