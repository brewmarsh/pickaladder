"""Tests for the group leaderboard."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from pickaladder.group.utils import get_group_leaderboard


class TestGroupLeaderboardSorting(unittest.TestCase):
    """Test case for the group leaderboard sorting."""

    @patch("pickaladder.group.utils.firestore")
    def test_leaderboard_sorting(self, mock_firestore: MagicMock) -> None:
        """Test the leaderboard is sorted by avg_score, then wins, then games_played."""
        # Mock Firestore client
        mock_db = mock_firestore.client.return_value

        # Create mock users
        def create_mock_user(uid: str, name: str) -> tuple[MagicMock, MagicMock]:
            """Create a pair of mock user reference and document snapshot."""
            doc = MagicMock()
            doc.id = uid
            doc.exists = True
            doc.to_dict.return_value = {"name": name}
            # Mock get() call on the reference
            ref = MagicMock()
            ref.id = uid
            ref.get.return_value = doc
            return ref, doc

        u1_ref, u1_doc = create_mock_user("u1", "User 1")  # Avg 11, 6 wins
        u2_ref, u2_doc = create_mock_user("u2", "User 2")  # Avg 11, 6 wins
        u3_ref, u3_doc = create_mock_user("u3", "User 3")  # Avg 12, 0 wins
        u4_ref, u4_doc = create_mock_user("u4", "Opponent")

        # Mock group data
        mock_group_doc = MagicMock()
        mock_group_doc.exists = True
        mock_group_doc.to_dict.return_value = {
            "members": [u1_ref, u2_ref, u3_ref, u4_ref]
        }
        mock_db.collection("groups").document(
            "group1"
        ).get.return_value = mock_group_doc

        matches = []

        def record_match(
            p1_ref: MagicMock, p1_score: int, p2_ref: MagicMock, p2_score: int
        ) -> MagicMock:
            """Create a mock match document."""
            m = MagicMock()
            m.to_dict.return_value = {
                "matchType": "singles",
                "player1Ref": p1_ref,
                "player1Score": p1_score,
                "player2Ref": p2_ref,
                "player2Score": p2_score,
            }
            return m

        # U1 wins 6 times with score 11
        for _ in range(6):
            matches.append(record_match(u1_ref, 11, u4_ref, 0))

        # U2 wins 6 times with score 11
        for _ in range(6):
            matches.append(record_match(u2_ref, 11, u4_ref, 0))

        # U3 loses 6 times with score 12 (against 13)
        for _ in range(6):
            matches.append(record_match(u3_ref, 12, u4_ref, 13))

        # We also need to mock group invites stream to be empty
        (
            mock_db.collection.return_value.where.return_value.where.return_value.stream.return_value
        ) = []

        # Matches query return value
        mock_db.collection.return_value.where.return_value.stream.return_value = matches

        # Running the function
        leaderboard = get_group_leaderboard("group1")

        # Assertions
        # Expect U3 to be first because Avg 12 > 11
        self.assertEqual(
            leaderboard[0]["id"], "u3", "Highest avg score (U3) should be first"
        )
        self.assertEqual(leaderboard[0]["avg_score"], 12.0)

        # U1 and U2 are tied at 11.0, and wins 6.
        # Order doesn't strictly matter between them, but they must be after U3.
        self.assertIn(leaderboard[1]["id"], ["u1", "u2"])
        self.assertIn(leaderboard[2]["id"], ["u1", "u2"])
        self.assertEqual(leaderboard[1]["avg_score"], 11.0)


if __name__ == "__main__":
    unittest.main()
