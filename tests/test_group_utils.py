"""Tests for the group utils."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from pickaladder.group.services.leaderboard import get_group_leaderboard
from pickaladder.group.services.stats import (
    get_head_to_head_stats,
    get_partnership_stats,
)


class TestGroupUtils(unittest.TestCase):
    """Test case for the group utils."""

    @patch("pickaladder.group.services.leaderboard.firestore")
    def test_get_group_leaderboard(self, mock_firestore: MagicMock) -> None:
        """Test the get_group_leaderboard function."""
        # Mock Firestore client
        mock_db = mock_firestore.client.return_value

        # Mock group data
        mock_group_doc = MagicMock()
        mock_group_doc.exists = True
        mock_group_doc.to_dict.return_value = {
            "members": [
                mock_db.collection("users").document("user1"),
                mock_db.collection("users").document("user2"),
            ]
        }
        mock_db.collection("groups").document(
            "group1"
        ).get.return_value = mock_group_doc

        # Mock user data
        mock_user1_doc = MagicMock()
        mock_user1_doc.exists = True
        mock_user1_doc.to_dict.return_value = {"name": "User 1"}
        mock_db.collection("users").document("user1").get.return_value = mock_user1_doc

        mock_user2_doc = MagicMock()
        mock_user2_doc.exists = True
        mock_user2_doc.to_dict.return_value = {"name": "User 2"}
        mock_db.collection("users").document("user2").get.return_value = mock_user2_doc

        # Mock match data
        mock_match1 = MagicMock()
        mock_match1.id = "match1"
        mock_match1.to_dict.return_value = {
            "player1Ref": mock_db.collection("users").document("user1"),
            "player2Ref": mock_db.collection("users").document("user2"),
            "player1Score": 11,
            "player2Score": 5,
        }

        # This is the key to the fix. We need to mock the return value of the
        # `where` clause for both player1Ref and player2Ref.
        mock_user1_ref = MagicMock()
        mock_user1_ref.id = "user1"
        mock_user1_ref.get.return_value = mock_user1_doc
        mock_user2_ref = MagicMock()
        mock_user2_ref.id = "user2"
        mock_user2_ref.get.return_value = mock_user2_doc
        member_refs = [mock_user1_ref, mock_user2_ref]
        mock_group_doc.to_dict.return_value["members"] = member_refs
        mock_match1.to_dict.return_value["player1Ref"] = mock_user1_ref
        mock_match1.to_dict.return_value["player2Ref"] = mock_user2_ref
        mock_db.collection.return_value.document.return_value.get.return_value = (
            mock_group_doc
        )
        mock_db.collection.return_value.where.return_value.stream.side_effect = [
            [mock_match1],
            [mock_match1],
        ]

        # Call the function
        leaderboard = get_group_leaderboard("group1")

        # Assert the results
        self.assertEqual(len(leaderboard), 2)
        self.assertEqual(leaderboard[0]["name"], "User 1")
        self.assertEqual(leaderboard[0]["wins"], 1)
        self.assertEqual(leaderboard[0]["losses"], 0)
        self.assertEqual(leaderboard[0]["avg_score"], 11.0)
        self.assertEqual(leaderboard[1]["name"], "User 2")
        self.assertEqual(leaderboard[1]["wins"], 0)
        self.assertEqual(leaderboard[1]["losses"], 1)
        self.assertEqual(leaderboard[1]["avg_score"], 5.0)

    def test_get_partnership_stats(self) -> None:
        """Test the get_partnership_stats function with old and new formats."""
        # Legacy format (IDs)
        match1 = MagicMock()
        match1.to_dict.return_value = {
            "matchType": "doubles",
            "player1Id": "user1",
            "partnerId": "user2",
            "player1Score": 11,
            "player2Score": 5,
        }

        # New format (Refs)
        ref1 = MagicMock()
        ref1.id = "user1"
        ref2 = MagicMock()
        ref2.id = "user2"
        match2 = MagicMock()
        match2.to_dict.return_value = {
            "matchType": "doubles",
            "team1": [ref1, ref2],
            "player1Score": 5,
            "player2Score": 11,
        }

        # Singles match (should be ignored)
        match3 = MagicMock()
        match3.to_dict.return_value = {
            "matchType": "singles",
            "player1Id": "user1",
            "player2Id": "user2",
            "player1Score": 11,
            "player2Score": 5,
        }

        matches = [match1, match2, match3]

        # Test partnership user1 and user2
        stats = get_partnership_stats("user1", "user2", matches)
        # match1: win, match2: loss
        self.assertEqual(stats["wins"], 1)
        self.assertEqual(stats["losses"], 1)

    @patch("pickaladder.group.services.stats.firestore")
    def test_get_head_to_head_stats(self, mock_firestore: MagicMock) -> None:
        """Test the get_head_to_head_stats function with mixed formats."""
        mock_db = mock_firestore.client.return_value

        # Match 1: user1 & user3 vs user2 & user4 (Legacy format)
        match1 = MagicMock()
        match1.id = "match1"
        match1.to_dict.return_value = {
            "matchType": "doubles",
            "player1Id": "user1",
            "partnerId": "user3",
            "player2Id": "user2",
            "opponent2Id": "user4",
            "player1Score": 11,
            "player2Score": 5,
        }

        # Match 2: user2 & user3 vs user1 & user4 (New format)
        ref1 = MagicMock()
        ref1.id = "user1"
        ref2 = MagicMock()
        ref2.id = "user2"
        ref3 = MagicMock()
        ref3.id = "user3"
        ref4 = MagicMock()
        ref4.id = "user4"

        match2 = MagicMock()
        match2.id = "match2"
        match2.to_dict.return_value = {
            "matchType": "doubles",
            "team1": [ref2, ref3],
            "team2": [ref1, ref4],
            "player1Score": 11,
            "player2Score": 5,
        }

        # Match 3: Partnership match (should be counted for chemistry but not rivalry)
        match3 = MagicMock()
        match3.id = "match3"
        match3.to_dict.return_value = {
            "matchType": "doubles",
            "team1": [ref1, ref2],
            "team2": [ref3, ref4],
            "player1Score": 11,
            "player2Score": 5,
        }

        mock_db.collection.return_value.where.return_value.stream.return_value = [
            match1,
            match2,
            match3,
        ]

        stats = get_head_to_head_stats("group1", "user1", "user2")

        # match1: user1 wins against user2
        # match2: user1 loses against user2
        self.assertEqual(stats["wins"], 1)
        self.assertEqual(stats["losses"], 1)
        self.assertEqual(len(stats["matches"]), 2)
        # match1 diff: 11-5=6, match2 diff: 5-11=-6
        self.assertEqual(stats["point_diff"], 0)

        # Chemistry (Partnership)
        # match3: user1 & user2 win together
        self.assertEqual(stats["partnership_record"]["wins"], 1)
        self.assertEqual(stats["partnership_record"]["losses"], 0)


if __name__ == "__main__":
    unittest.main()
