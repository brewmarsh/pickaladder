from __future__ import annotations

import unittest
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, patch

from pickaladder import create_app


class MockDocumentReference:
    def __init__(self, id: str | None = None) -> None:
        self.id = id
        self.path = f"collection/{id}" if id else "collection/unknown"
        self.get = MagicMock()
        self.collection = MagicMock()


class BestBudsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_firestore_service = MagicMock()
        self.mock_firestore_service.DocumentReference = MockDocumentReference

        # Mock collection().document() to return an object with the right id
        def mock_document(doc_id: str) -> MockDocumentReference:
            return MockDocumentReference(doc_id)

        (
            self.mock_firestore_service.client.return_value.collection.return_value.document.side_effect
        ) = mock_document

        # Patch firestore in multiple places
        self.patchers = [
            patch(
                "pickaladder.group.routes.firestore", new=self.mock_firestore_service
            ),
            patch("pickaladder.firestore", new=self.mock_firestore_service),
        ]
        for p in self.patchers:
            p.start()

        self.app = create_app({"TESTING": True, "WTF_CSRF_ENABLED": False})
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self) -> None:
        for p in self.patchers:
            p.stop()
        self.app_context.pop()

    @patch("pickaladder.group.routes.get_group_leaderboard", return_value=[])
    def test_best_buds_identification(self, mock_leaderboard: MagicMock) -> None:
        # Set session
        with self.client.session_transaction() as sess:
            sess["user_id"] = "user1"

        mock_db = self.mock_firestore_service.client.return_value

        # Mock g.user load
        user1_data = {"username": "User1", "name": "User 1"}
        mock_user1_doc = MagicMock()
        mock_user1_doc.exists = True
        mock_user1_doc.to_dict.return_value = user1_data
        mock_db.collection("users").document("user1").get.return_value = mock_user1_doc

        group_id = "group1"

        # Mock group
        mock_group_ref = mock_db.collection("groups").document(group_id)
        mock_group_doc = MagicMock()
        mock_group_doc.exists = True

        user_ref1 = MagicMock()
        user_ref1.id = "user1"
        user_ref1.path = "users/user1"

        user_ref2 = MagicMock()
        user_ref2.id = "user2"
        user_ref2.path = "users/user2"

        mock_group_doc.to_dict.return_value = {
            "name": "Test Group",
            "members": [user_ref1, user_ref2],
            "ownerRef": user_ref1,
        }
        mock_group_ref.get.return_value = mock_group_doc

        # Mock members
        user_doc1 = MagicMock()
        user_doc1.exists = True
        user_doc1.id = "user1"
        user_doc1.to_dict.return_value = {"username": "User1", "name": "User 1"}
        user_ref1.get.return_value = user_doc1

        user_doc2 = MagicMock()
        user_doc2.exists = True
        user_doc2.id = "user2"
        user_doc2.to_dict.return_value = {"username": "User2", "name": "User 2"}
        user_ref2.get.return_value = user_doc2

        # Mock teams query
        mock_teams_collection = mock_db.collection("teams")
        mock_query = mock_teams_collection.where.return_value

        team1_doc = MagicMock()
        team1_doc.id = "team1"
        team1_doc.exists = True
        team1_doc.to_dict.return_value = {
            "member_ids": ["user1", "user2"],
            "members": [user_ref1, user_ref2],
            "stats": {"wins": 10, "losses": 2},
            "name": "User 1 & User 2",
        }

        team2_doc = MagicMock()
        team2_doc.id = "team2"
        team2_doc.exists = True
        team2_doc.to_dict.return_value = {
            "member_ids": ["user1", "other"],
            "members": [user_ref1, MockDocumentReference("other")],
            "stats": {"wins": 20, "losses": 1},
            "name": "User 1 & Other",
        }

        mock_query.stream.return_value = [team1_doc, team2_doc]

        # Mock get_all for both teams and team members enrichment
        def mock_get_all(refs: list[Any]) -> list[Any]:
            results = []
            for ref in refs:
                if ref.id == "team1":
                    results.append(team1_doc)
                elif ref.id == "team2":
                    results.append(team2_doc)
                elif ref.id == "user1":
                    results.append(user_doc1)
                elif ref.id == "user2":
                    results.append(user_doc2)
            return results

        mock_db.get_all.side_effect = mock_get_all

        # Mock matches query - Now required for best buds calculation
        match_doc = MagicMock()
        # Mocking the team references
        team1_ref = MockDocumentReference("team1")
        team2_ref = MockDocumentReference("team2")

        match_doc.to_dict.return_value = {
            "matchType": "doubles",
            "team1Ref": team1_ref,
            "team2Ref": team2_ref,
            "player1Score": 11,
            "player2Score": 5,
            "groupId": group_id,
            "matchDate": datetime.now(),
        }
        (
            mock_db.collection(
                "matches"
            ).where.return_value.order_by.return_value.limit.return_value.stream.return_value
        ) = [match_doc] * 10

        # Mock friends query for the invite form
        (
            mock_db.collection("users")
            .document("user1")
            .collection("friends")
            .where.return_value.stream.return_value
        ) = []

        response = self.client.get(f"/group/{group_id}")

        self.assertEqual(response.status_code, 200)
        # team1 should be best buds because team2 has a member not in group
        self.assertIn(b"Best Buds", response.data)
        self.assertIn(b"User 1", response.data)
        self.assertIn(b"User 2", response.data)
        self.assertIn(b"10 Wins Together!", response.data)
        # Team 2 should NOT be best buds even though it has more wins (20)
        self.assertNotIn(b"20 Wins Together!", response.data)


if __name__ == "__main__":
    unittest.main()
