import unittest
from unittest.mock import patch, MagicMock
import datetime

# Pre-emptive imports to ensure patch targets exist.

from pickaladder import create_app

# Mock user payloads
MOCK_USER_ID = "winner_uid"
MOCK_USER_PAYLOAD = {"uid": MOCK_USER_ID, "email": "winner@example.com"}
MOCK_USER_DATA = {"name": "Winner", "isAdmin": False}

MOCK_OPPONENT_ID = "loser_uid"
MOCK_OPPONENT_PAYLOAD = {"uid": MOCK_OPPONENT_ID, "email": "loser@example.com"}
MOCK_OPPONENT_DATA = {"name": "Loser", "isAdmin": False}


class MatchRoutesFirebaseTestCase(unittest.TestCase):

    def setUp(self):
        """Set up a test client and a comprehensive mock environment."""
        self.mock_auth_service = MagicMock()
        self.mock_firestore_service = MagicMock()

        patchers = {
            'init_app': patch('firebase_admin.initialize_app'),
            # Patch for the `before_request` user loader in `__init__.py`.
            'init_firebase_admin': patch('pickaladder.firebase_admin'),
            'init_firestore': patch('pickaladder.firestore', new=self.mock_firestore_service),
            # Patch for the match routes.
            'match_routes_firestore': patch('pickaladder.match.routes.firestore', new=self.mock_firestore_service),
            # Patch for the login route, which can be a redirect target.
            'auth_routes_firestore': patch('pickaladder.auth.routes.firestore', new=self.mock_firestore_service),
        }

        self.mocks = {name: p.start() for name, p in patchers.items()}
        for p in patchers.values():
            self.addCleanup(p.stop)

        self.mocks['init_firebase_admin'].auth = self.mock_auth_service

        self.app = create_app({
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SERVER_NAME": "localhost"
        })
        self.client = self.app.test_client()

    def _simulate_login(self):
        """Configure mocks for a logged-in user."""
        self.mock_auth_service.verify_id_token.return_value = MOCK_USER_PAYLOAD

        mock_db = self.mock_firestore_service.client.return_value
        mock_users_collection = mock_db.collection('users')

        # Mock the logged-in user's document
        mock_user_doc = mock_users_collection.document(MOCK_USER_ID)
        mock_user_snapshot = MagicMock()
        mock_user_snapshot.exists = True
        mock_user_snapshot.to_dict.return_value = MOCK_USER_DATA
        mock_user_doc.get.return_value = mock_user_snapshot

        # Mock the opponent's document
        mock_opponent_doc = mock_users_collection.document(MOCK_OPPONENT_ID)
        mock_opponent_snapshot = MagicMock()
        mock_opponent_snapshot.exists = True
        mock_opponent_snapshot.to_dict.return_value = MOCK_OPPONENT_DATA
        mock_opponent_doc.get.return_value = mock_opponent_snapshot

        # Mock the admin check in the login route to prevent redirects to /install.
        mock_db.collection('users').where.return_value.limit.return_value.get.return_value = [MagicMock()]

        return {"Authorization": "Bearer mock-token"}

    def test_create_match(self):
        """Test creating a new match."""
        headers = self._simulate_login()

        mock_db = self.mock_firestore_service.client.return_value
        mock_matches_collection = mock_db.collection('matches')

        # The create match form needs to populate the opponent dropdown.
        # Mock the query for the user's friends.
        mock_friends_query = mock_db.collection('users').document(MOCK_USER_ID).collection('friends').where.return_value
        mock_friend_ref = MagicMock()
        mock_friend_ref.id = MOCK_OPPONENT_ID
        mock_friends_query.stream.return_value = [mock_friend_ref]

        # Mock the query to get the friend's user data.
        mock_opponent_user_query = mock_db.collection('users').where.return_value
        mock_opponent_user_doc = MagicMock()
        mock_opponent_user_doc.id = MOCK_OPPONENT_ID
        mock_opponent_user_doc.to_dict.return_value = MOCK_OPPONENT_DATA
        mock_opponent_user_query.stream.return_value = [mock_opponent_user_doc]

        response = self.client.post(
            "/match/create",
            headers=headers,
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