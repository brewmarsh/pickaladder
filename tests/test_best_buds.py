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
            patch(
                "pickaladder.group.services.group_service.firestore",
                new=self.mock_firestore_service,
            ),
            patch("pickaladder.group.utils.firestore", new=self.mock_firestore_service),
            patch("pickaladder.firestore", new=self.mock_firestore_service),
            patch("firebase_admin.initialize_app"),
            patch("firebase_admin.get_app"),
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

    @patch("pickaladder.group.services.group_service.get_group_leaderboard")
    def test_best_buds_identification(
        self, mock_leaderboard_service: MagicMock
    ) -> None:
        # Arrange
        group_id = "group1"
        self._setup_best_buds_data(mock_leaderboard_service, group_id)

        # Act
        response = self.client.get(f"/group/{group_id}")

        # Assert
        self._verify_best_buds_response(response)

    def _setup_best_buds_data(
        self, mock_leaderboard_service: MagicMock, group_id: str
    ) -> None:
        self._mock_leaderboard(mock_leaderboard_service)
        with self.client.session_transaction() as sess:
            sess["user_id"] = "user1"

        mock_db = self.mock_firestore_service.client.return_value
        user_docs = self._setup_users(mock_db)
        self._setup_group(mock_db, group_id, user_docs)
        team_docs = self._setup_teams(mock_db, user_docs)
        self._setup_get_all(mock_db, user_docs, team_docs)
        self._setup_matches(mock_db, group_id)
        self._setup_friends(mock_db, "user1")

    def _mock_leaderboard(self, mock_service: MagicMock) -> None:
        mock_service.return_value = [
            {
                "id": "user1",
                "name": "Alice",
                "wins": 10,
                "losses": 2,
                "avg_score": 11.0,
                "form": ["W", "W", "W", "W", "W"],
            },
            {
                "id": "user2",
                "name": "Bob",
                "wins": 8,
                "losses": 4,
                "avg_score": 9.5,
                "form": ["W", "L", "W", "W", "L"],
            },
        ]

    def _setup_users(self, mock_db: MagicMock) -> dict[str, MagicMock]:
        user_doc1 = MagicMock(exists=True, id="user1")
        user_doc1.to_dict.return_value = {"username": "User1", "name": "User 1"}
        mock_db.collection("users").document("user1").get.return_value = user_doc1

        user_doc2 = MagicMock(exists=True, id="user2")
        user_doc2.to_dict.return_value = {"username": "User2", "name": "User 2"}

        return {"user1": user_doc1, "user2": user_doc2}

    def _setup_group(
        self, mock_db: MagicMock, group_id: str, user_docs: dict[str, MagicMock]
    ) -> None:
        mock_group_ref = mock_db.collection("groups").document(group_id)
        mock_group_doc = MagicMock(exists=True)

        user_ref1 = MagicMock(id="user1", path="users/user1")
        user_ref1.get.return_value = user_docs["user1"]
        user_ref2 = MagicMock(id="user2", path="users/user2")
        user_ref2.get.return_value = user_docs["user2"]

        mock_group_doc.to_dict.return_value = {
            "name": "Test Group",
            "members": [user_ref1, user_ref2],
            "ownerRef": user_ref1,
        }
        mock_group_ref.get.return_value = mock_group_doc

    def _setup_teams(
        self, mock_db: MagicMock, user_docs: dict[str, MagicMock]
    ) -> dict[str, MagicMock]:
        user_ref1 = MagicMock(id="user1")
        user_ref2 = MagicMock(id="user2")
        other_ref = MockDocumentReference("other")

        team1_doc = MagicMock(id="team1", exists=True)
        team1_doc.to_dict.return_value = {
            "member_ids": ["user1", "user2"],
            "members": [user_ref1, user_ref2],
            "stats": {"wins": 10, "losses": 2},
            "name": "User 1 & User 2",
        }

        team2_doc = MagicMock(id="team2", exists=True)
        team2_doc.to_dict.return_value = {
            "member_ids": ["user1", "other"],
            "members": [user_ref1, other_ref],
            "stats": {"wins": 20, "losses": 1},
            "name": "User 1 & Other",
        }

        mock_db.collection("teams").where.return_value.stream.return_value = [
            team1_doc,
            team2_doc,
        ]
        return {"team1": team1_doc, "team2": team2_doc}

    def _setup_get_all(
        self,
        mock_db: MagicMock,
        user_docs: dict[str, MagicMock],
        team_docs: dict[str, MagicMock],
    ) -> None:
        def mock_get_all(refs: list[Any]) -> list[Any]:
            all_docs = {**user_docs, **team_docs}
            return [all_docs.get(ref.id) for ref in refs if ref.id in all_docs]

        mock_db.get_all.side_effect = mock_get_all

    def _setup_matches(self, mock_db: MagicMock, group_id: str) -> None:
        match_doc = MagicMock()
        match_doc.to_dict.return_value = {
            "matchType": "doubles",
            "team1Ref": MockDocumentReference("team1"),
            "team2Ref": MockDocumentReference("team2"),
            "player1Score": 11,
            "player2Score": 5,
            "groupId": group_id,
            "matchDate": datetime.now(),
        }
        (
            mock_db.collection("matches")
            .where.return_value.order_by.return_value.limit.return_value.stream.return_value
        ) = [match_doc] * 10

    def _setup_friends(self, mock_db: MagicMock, user_id: str) -> None:
        (
            mock_db.collection("users")
            .document(user_id)
            .collection("friends")
            .where.return_value.stream.return_value
        ) = []

    def _verify_best_buds_response(self, response: Any) -> None:
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Best Buds", response.data)
        self.assertIn(b"User 1", response.data)
        self.assertIn(b"User 2", response.data)
        self.assertIn(b"10 Wins Together!", response.data)
        self.assertNotIn(b"20 Wins Together!", response.data)


if __name__ == "__main__":
    unittest.main()
