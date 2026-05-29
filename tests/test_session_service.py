import unittest
from unittest.mock import MagicMock, patch

from pickaladder.group.services.session_service import SessionService


class TestSessionService(unittest.TestCase):
    def setUp(self) -> None:
        self.db = MagicMock()
        self.group_id = "test_group"
        self.creator_id = "test_user"
        self.player_ids = ["user1", "user2", "user3"]

    def test_create_session(self) -> None:
        # Mocking cls.create (inherited from BaseRepository)
        with patch("pickaladder.base.repository.BaseRepository.create") as mock_create:
            mock_create.return_value = "new_session_id"

            session_id = SessionService.create_session(
                self.db,
                self.group_id,
                self.creator_id,
                self.player_ids,
            )

            assert session_id == "new_session_id"
            mock_create.assert_called_once()
            args, _ = mock_create.call_args
            data = args[1]
            assert data["groupId"] == self.group_id
            assert data["createdBy"] == self.creator_id
            assert data["playerIds"] == self.player_ids
            assert data["matchIds"] == []
            assert data["status"] == "ACTIVE"

    def test_get_session(self) -> None:
        with patch("pickaladder.base.repository.BaseRepository.get_by_id") as mock_get:
            mock_get.return_value = {"id": "session_123", "status": "ACTIVE"}

            session = SessionService.get_session(self.db, "session_123")

            assert session["id"] == "session_123"
            mock_get.assert_called_once_with(self.db, "session_123")

    def test_add_match_to_session(self) -> None:
        mock_doc = MagicMock()
        self.db.collection.return_value.document.return_value = mock_doc

        with patch("firebase_admin.firestore.ArrayUnion") as mock_union:
            mock_union.return_value = "mock_union"

            SessionService.add_match_to_session(self.db, "session_123", "match_456")

            self.db.collection.assert_called_with("sessions")
            self.db.collection().document.assert_called_with("session_123")
            mock_doc.update.assert_called_once()
            update_data = mock_doc.update.call_args[0][0]
            assert update_data["matchIds"] == "mock_union"
            mock_union.assert_called_once_with(["match_456"])

    def test_verify_session_already_verified(self) -> None:
        session_data = {
            "id": "session_123",
            "playerIds": ["user1", "user2"],
            "verifiedBy": ["user1"],
            "status": "ACTIVE",
        }
        with patch.object(SessionService, "get_session", return_value=session_data):
            success = SessionService.verify_session(self.db, "session_123", "user1")
            assert success
            self.db.collection.return_value.document.return_value.update.assert_not_called()

    def test_verify_session_completes(self) -> None:
        session_data = {
            "id": "session_123",
            "playerIds": ["user1", "user2"],
            "verifiedBy": ["user1"],
            "matchIds": ["match1", "match2"],
            "status": "ACTIVE",
        }
        mock_doc = MagicMock()
        self.db.collection.return_value.document.return_value = mock_doc
        mock_batch = MagicMock()
        self.db.batch.return_value = mock_batch

        with patch.object(SessionService, "get_session", return_value=session_data):
            success = SessionService.verify_session(self.db, "session_123", "user2")

            assert success
            # Check session status update in batch
            mock_batch.update.assert_any_call(
                mock_doc,
                {"status": "COMPLETED", "updatedAt": unittest.mock.ANY},
            )
            # Check match updates in batch
            assert mock_batch.update.call_count == 3  # 1 session + 2 matches
            mock_batch.commit.assert_called_once()

    def test_verify_session_unauthorized(self) -> None:
        session_data = {
            "id": "session_123",
            "playerIds": ["user1", "user2"],
            "verifiedBy": [],
            "status": "ACTIVE",
        }
        with patch.object(SessionService, "get_session", return_value=session_data):
            success = SessionService.verify_session(
                self.db,
                "session_123",
                "user_random",
            )
            assert not success


if __name__ == "__main__":
    unittest.main()
