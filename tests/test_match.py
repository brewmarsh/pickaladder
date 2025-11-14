"""Tests for the match blueprint."""

import datetime
import unittest
from unittest.mock import MagicMock, patch

# Pre-emptive imports to ensure patch targets exist.
from pickaladder import create_app
from pickaladder.match import routes

# Mock user payloads
MOCK_USER_ID = "winner_uid"
MOCK_USER_PAYLOAD = {"uid": MOCK_USER_ID, "email": "winner@example.com"}
MOCK_USER_DATA = {"name": "Winner", "isAdmin": False}

MOCK_OPPONENT_ID = "loser_uid"
MOCK_OPPONENT_PAYLOAD = {"uid": MOCK_OPPONENT_ID, "email": "loser@example.com"}
MOCK_OPPONENT_DATA = {"name": "Loser", "isAdmin": False}


class MatchRoutesFirebaseTestCase(unittest.TestCase):
    """Test case for the match blueprint."""

    def setUp(self):
        """Set up a test client and a comprehensive mock environment."""
        self.mock_firestore_service = MagicMock()

        patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            "db": patch("pickaladder.match.routes.db", new=self.mock_firestore_service),
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

    def tearDown(self):
        """Tear down the test client."""
        self.app_context.pop()

    def _set_session_user(self):
        with self.client.session_transaction() as sess:
            sess["user_id"] = MOCK_USER_ID
            sess["is_admin"] = False
        self.mocks["verify_id_token"].return_value = MOCK_USER_PAYLOAD

    def _get_auth_headers(self):
        return {"Authorization": "Bearer mock-token"}

    def test_create_match(self):
        """Test creating a new match."""
        self._set_session_user()

        mock_db = self.mock_firestore_service.client.return_value
        mock_users_collection = mock_db.collection("users")

        mock_user_doc = mock_users_collection.document(MOCK_USER_ID)
        mock_user_snapshot = MagicMock()
        mock_user_snapshot.exists = True
        mock_user_snapshot.to_dict.return_value = MOCK_USER_DATA
        mock_user_doc.get.return_value = mock_user_snapshot

        mock_opponent_doc = mock_users_collection.document(MOCK_OPPONENT_ID)
        mock_opponent_snapshot = MagicMock()
        mock_opponent_snapshot.exists = True
        mock_opponent_snapshot.to_dict.return_value = MOCK_OPPONENT_DATA
        mock_opponent_doc.get.return_value = mock_opponent_snapshot

        mock_matches_collection = mock_db.collection("matches")

        mock_friends_query = (
            mock_db.collection("users")
            .document(MOCK_USER_ID)
            .collection("friends")
            .where.return_value
        )
        mock_friend_ref = MagicMock()
        mock_friend_ref.id = MOCK_OPPONENT_ID
        mock_friends_query.stream.return_value = [mock_friend_ref]

        mock_opponent_user_query = mock_db.collection("users").where.return_value
        mock_opponent_user_doc = MagicMock()
        mock_opponent_user_doc.id = MOCK_OPPONENT_ID
        mock_opponent_user_doc.to_dict.return_value = MOCK_OPPONENT_DATA
        mock_opponent_user_query.stream.return_value = [mock_opponent_user_doc]

        response = self.client.post(
            "/match/create",
            headers=self._get_auth_headers(),
            data={
                "player2": MOCK_OPPONENT_ID,
                "player1_score": 11,
                "player2_score": 5,
                "match_date": datetime.date.today().isoformat(),
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Match created successfully.", response.data)
        mock_matches_collection.add.assert_called_once()


if __name__ == "__main__":
    unittest.main()
