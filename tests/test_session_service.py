import unittest
from unittest.mock import MagicMock, patch
from pickaladder.group.services.session_service import SessionService

class TestSessionService(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.group_id = "test_group"
        self.creator_id = "test_user"
        self.player_ids = ["user1", "user2", "user3"]

    def test_create_session(self):
        # Mocking cls.create (inherited from BaseRepository)
        with patch("pickaladder.base.repository.BaseRepository.create") as mock_create:
            mock_create.return_value = "new_session_id"
            
            session_id = SessionService.create_session(
                self.db, self.group_id, self.creator_id, self.player_ids
            )
            
            self.assertEqual(session_id, "new_session_id")
            mock_create.assert_called_once()
            args, _ = mock_create.call_args
            data = args[1]
            self.assertEqual(data["groupId"], self.group_id)
            self.assertEqual(data["createdBy"], self.creator_id)
            self.assertEqual(data["playerIds"], self.player_ids)
            self.assertEqual(data["matchIds"], [])
            self.assertEqual(data["status"], "ACTIVE")

    def test_get_session(self):
        with patch("pickaladder.base.repository.BaseRepository.get_by_id") as mock_get:
            mock_get.return_value = {"id": "session_123", "status": "ACTIVE"}
            
            session = SessionService.get_session(self.db, "session_123")
            
            self.assertEqual(session["id"], "session_123")
            mock_get.assert_called_once_with(self.db, "session_123")

    def test_add_match_to_session(self):
        mock_doc = MagicMock()
        self.db.collection.return_value.document.return_value = mock_doc
        
        with patch("firebase_admin.firestore.ArrayUnion") as mock_union:
            mock_union.return_value = "mock_union"
            
            SessionService.add_match_to_session(self.db, "session_123", "match_456")
            
            self.db.collection.assert_called_with("sessions")
            self.db.collection().document.assert_called_with("session_123")
            mock_doc.update.assert_called_once()
            update_data = mock_doc.update.call_args[0][0]
            self.assertEqual(update_data["matchIds"], "mock_union")
            mock_union.assert_called_once_with(["match_456"])

if __name__ == "__main__":
    unittest.main()
