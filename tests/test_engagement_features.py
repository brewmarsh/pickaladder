import unittest
from unittest.mock import MagicMock, patch
from typing import Any, cast
import datetime
from pickaladder.user.services.match_stats import calculate_current_streak, get_recent_opponents

class TestEngagementFeatures(unittest.TestCase):
    def setUp(self):
        self.user_id = "user1"
        self.db = MagicMock()

    def test_calculate_current_streak(self):
        # Case 1: Multiple wins followed by a loss
        matches = [
            # Recent to oldest
            {"matchDate": datetime.datetime(2023, 1, 5), "player1Ref": MagicMock(id="user1"), "player1Score": 11, "player2Score": 5, "matchType": "singles"}, # Win
            {"matchDate": datetime.datetime(2023, 1, 4), "player1Ref": MagicMock(id="user1"), "player1Score": 11, "player2Score": 8, "matchType": "singles"}, # Win
            {"matchDate": datetime.datetime(2023, 1, 3), "player1Ref": MagicMock(id="user1"), "player1Score": 11, "player2Score": 9, "matchType": "singles"}, # Win
            {"matchDate": datetime.datetime(2023, 1, 2), "player1Ref": MagicMock(id="user1"), "player1Score": 5, "player2Score": 11, "matchType": "singles"}, # Loss
            {"matchDate": datetime.datetime(2023, 1, 1), "player1Ref": MagicMock(id="user1"), "player1Score": 11, "player2Score": 0, "matchType": "singles"}, # Win (ignored)
        ]
        self.assertEqual(calculate_current_streak(self.user_id, matches), 3)

        # Case 2: Latest is a loss
        matches = [
            {"matchDate": datetime.datetime(2023, 1, 5), "player1Ref": MagicMock(id="user1"), "player1Score": 5, "player2Score": 11, "matchType": "singles"}, # Loss
            {"matchDate": datetime.datetime(2023, 1, 4), "player1Ref": MagicMock(id="user1"), "player1Score": 11, "player2Score": 8, "matchType": "singles"}, # Win
        ]
        self.assertEqual(calculate_current_streak(self.user_id, matches), 0)

        # Case 3: Empty matches
        self.assertEqual(calculate_current_streak(self.user_id, []), 0)

        # Case 4: No losses in history
        matches = [
            {"matchDate": datetime.datetime(2023, 1, 5), "player1Ref": MagicMock(id="user1"), "player1Score": 11, "player2Score": 5, "matchType": "singles"}, # Win
            {"matchDate": datetime.datetime(2023, 1, 4), "player1Ref": MagicMock(id="user1"), "player1Score": 11, "player2Score": 8, "matchType": "singles"}, # Win
        ]
        self.assertEqual(calculate_current_streak(self.user_id, matches), 2)

    def test_get_recent_opponents(self):
        mock_user2 = {"username": "user2", "uid": "user2"}
        mock_user3 = {"username": "user3", "uid": "user3"}

        matches = [
            {"matchType": "singles", "player1Ref": MagicMock(id="user1"), "player2Ref": MagicMock(id="user2")},
            {"matchType": "singles", "player1Ref": MagicMock(id="user3"), "player2Ref": MagicMock(id="user1")},
            {"matchType": "doubles", "team1": [MagicMock(id="user1"), MagicMock(id="user4")], "team2": [MagicMock(id="user2"), MagicMock(id="user3")]}, # Ignored
            {"matchType": "singles", "player1Ref": MagicMock(id="user1"), "player2Ref": MagicMock(id="user2")}, # Duplicate user2
        ]

        mock_doc2 = MagicMock()
        mock_doc2.exists = True
        mock_doc2.id = "user2"
        mock_doc2.to_dict.return_value = {"username": "user2"}

        mock_doc3 = MagicMock()
        mock_doc3.exists = True
        mock_doc3.id = "user3"
        mock_doc3.to_dict.return_value = {"username": "user3"}

        self.db.get_all.return_value = [mock_doc2, mock_doc3]

        opponents = get_recent_opponents(self.db, self.user_id, matches, limit=4)

        self.assertEqual(len(opponents), 2)
        self.assertEqual(opponents[0]["id"], "user2")
        self.assertEqual(opponents[1]["id"], "user3")
        # Check if uid is set as requested
        self.assertEqual(opponents[0]["uid"], "user2")

if __name__ == "__main__":
    unittest.main()
