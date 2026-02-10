"""Tests for the rematch logic in match recording."""

import unittest
from unittest.mock import MagicMock, patch
from pickaladder import create_app

class RematchLogicTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SERVER_NAME": "localhost",
        })
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    @patch("pickaladder.match.routes.firestore.client")
    @patch("pickaladder.match.routes.MatchService.get_candidate_player_ids")
    def test_record_match_prepopulation(self, mock_get_candidates, mock_firestore_client):
        # Mocking necessary parts for the record_match route
        mock_get_candidates.return_value = {"user1", "user2", "user3", "user4"}

        # Mock firestore client for choices population
        mock_db = MagicMock()
        mock_firestore_client.return_value = mock_db

        def mock_get_all(refs):
            docs = []
            for ref in refs:
                doc = MagicMock()
                doc.exists = True
                doc.id = ref.id
                doc.to_dict.return_value = {"name": f"Name {ref.id}"}
                docs.append(doc)
            return docs
        mock_db.get_all.side_effect = mock_get_all

        # Mock session
        with self.client.session_transaction() as sess:
            sess["user_id"] = "user1"

        # Add a patch for verify_id_token to mock authentication
        with patch("firebase_admin.auth.verify_id_token") as mock_verify:
            mock_verify.return_value = {"uid": "user1", "email": "user1@example.com"}

            # Test doubles pre-population
            response = self.client.get(
                "/match/record?match_type=doubles&player1=user1&player2=user2&player3=user3&player4=user4",
                headers={"Authorization": "Bearer mock-token"}
            )

            self.assertEqual(response.status_code, 200)
            data = response.data.decode("utf-8")

            # Use more flexible checks
            self.assertTrue('value="doubles"' in data and 'selected' in data)
            self.assertIn('value="user1"', data)
            self.assertIn('value="user2"', data)
            self.assertIn('value="user3"', data)
            self.assertIn('value="user4"', data)

            # Check for selected attribute specifically in the options we expect
            self.assertIn('<option selected value="doubles">', data)
            self.assertIn('<option selected value="user1">', data)
            self.assertIn('<option selected value="user2">', data)
            self.assertIn('<option selected value="user3">', data)
            self.assertIn('<option selected value="user4">', data)

if __name__ == "__main__":
    unittest.main()
