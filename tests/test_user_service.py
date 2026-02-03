import unittest
from unittest.mock import MagicMock, patch

from pickaladder.user.utils import UserService


class TestUserService(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.user_id = "test_user_id"

    def test_get_user_by_id(self):
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"username": "testuser"}
        self.db.collection().document().get.return_value = mock_doc

        result = UserService.get_user_by_id(self.db, self.user_id)
        self.assertEqual(result["id"], self.user_id)
        self.assertEqual(result["username"], "testuser")

    def test_get_user_by_id_not_found(self):
        mock_doc = MagicMock()
        mock_doc.exists = False
        self.db.collection().document().get.return_value = mock_doc

        result = UserService.get_user_by_id(self.db, self.user_id)
        self.assertIsNone(result)

    def test_get_friendship_info_is_friend(self):
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"status": "accepted"}
        self.db.collection().document().collection().document().get.return_value = (
            mock_doc
        )

        is_friend, request_sent = UserService.get_friendship_info(
            self.db, "user1", "user2"
        )
        self.assertTrue(is_friend)
        self.assertFalse(request_sent)

    def test_get_friendship_info_pending(self):
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"status": "pending"}
        self.db.collection().document().collection().document().get.return_value = (
            mock_doc
        )

        is_friend, request_sent = UserService.get_friendship_info(
            self.db, "user1", "user2"
        )
        self.assertFalse(is_friend)
        self.assertTrue(request_sent)

    def test_get_user_friends(self):
        mock_f1 = MagicMock()
        mock_f1.id = "friend1"
        self.db.collection().document().collection().where().stream.return_value = [
            mock_f1
        ]

        mock_doc1 = MagicMock()
        mock_doc1.exists = True
        mock_doc1.id = "friend1"
        mock_doc1.to_dict.return_value = {"username": "friend_user"}
        self.db.get_all.return_value = [mock_doc1]

        result = UserService.get_user_friends(self.db, self.user_id)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["id"], "friend1")

    def test_calculate_stats(self):
        mock_match1 = MagicMock()
        mock_match1.to_dict.return_value = {
            "matchType": "singles",
            "player1Ref": MagicMock(id=self.user_id),
            "player1Score": 11,
            "player2Score": 5,
        }
        mock_match1.create_time = 100

        mock_match2 = MagicMock()
        mock_match2.to_dict.return_value = {
            "matchType": "singles",
            "player1Ref": MagicMock(id=self.user_id),
            "player1Score": 5,
            "player2Score": 11,
        }
        mock_match2.create_time = 200

        stats = UserService.calculate_stats([mock_match1, mock_match2], self.user_id)
        self.assertEqual(stats["wins"], 1)
        self.assertEqual(stats["losses"], 1)
        self.assertEqual(stats["total_games"], 2)
        # Match 2 is later (create_time 200) and was a loss. Match 1 was a win.
        # Streak calculation should see the latest match (loss) first.
        self.assertEqual(stats["current_streak"], 1)
        self.assertEqual(stats["streak_type"], "L")

    @patch("pickaladder.group.utils.get_group_leaderboard")
    def test_get_group_rankings(self, mock_leaderboard):
        mock_group = MagicMock()
        mock_group.id = "group1"
        mock_group.to_dict.return_value = {"name": "Test Group"}
        self.db.collection().where().stream.return_value = [mock_group]

        mock_leaderboard.return_value = [
            {"id": "other", "name": "Other", "avg_score": 100},
            {"id": self.user_id, "name": "Me", "avg_score": 50},
        ]

        rankings = UserService.get_group_rankings(self.db, self.user_id)
        self.assertEqual(len(rankings), 1)
        self.assertEqual(rankings[0]["rank"], 2)
        self.assertEqual(rankings[0]["group_name"], "Test Group")


if __name__ == "__main__":
    unittest.main()
