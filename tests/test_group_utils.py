import unittest
from unittest.mock import patch, MagicMock
from pickaladder.group.utils import get_group_leaderboard

class TestGroupUtils(unittest.TestCase):
    @patch("pickaladder.group.utils.firestore")
    def test_get_group_leaderboard(self, mock_firestore):
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
        mock_db.collection("groups").document("group1").get.return_value = mock_group_doc

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

        # This is the key to the fix. We need to mock the return value of the `where` clause
        # This is the key to the fix. We need to mock the return value of the `where` clause
        # This is the key to the fix. We need to mock the return value of the `where` clause
        # This is the key to the fix. We need to mock the return value of the `where` clause
        # This is the key to the fix. We need to mock the return value of the `where` clause
        # This is the key to the fix. We need to mock the return value of the `where` clause
        # This is the key to the fix. We need to mock the return value of the `where` clause
        # This is the key to the fix. We need to mock the return value of the `where` clause
        # for both player1Ref and player2Ref.
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
        mock_db.collection.return_value.document.return_value.get.return_value = mock_group_doc
        mock_db.collection.return_value.where.return_value.stream.side_effect = [[mock_match1], [mock_match1]]

        # Call the function
        leaderboard = get_group_leaderboard("group1")

        # Assert the results
        self.assertEqual(len(leaderboard), 2)
        self.assertEqual(leaderboard[0]["name"], "User 1")
        self.assertEqual(leaderboard[0]["wins"], 1)
        self.assertEqual(leaderboard[0]["losses"], 0)
        self.assertEqual(leaderboard[1]["name"], "User 2")
        self.assertEqual(leaderboard[1]["wins"], 0)
        self.assertEqual(leaderboard[1]["losses"], 1)

if __name__ == "__main__":
    unittest.main()
