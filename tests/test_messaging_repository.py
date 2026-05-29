import unittest
from unittest.mock import MagicMock, patch

from pickaladder.messaging.repository import MessagingRepository


class TestMessagingRepository(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_db = MagicMock()
        self.mock_batch = MagicMock()
        self.mock_db.batch.return_value = self.mock_batch

    @patch("pickaladder.messaging.repository.MessagingRepository.get_by_id")
    def test_add_message_updates_metadata(self, mock_get_by_id) -> None:
        # Setup
        conv_id = "conv123"
        sender_id = "user1"
        recipient_id = "user2"
        message_data = {"senderId": sender_id, "content": "Hello"}

        mock_conv_ref = MagicMock()
        self.mock_db.collection.return_value.document.return_value = mock_conv_ref

        mock_conv_doc = MagicMock()
        mock_conv_doc.exists = True
        mock_conv_doc.to_dict.return_value = {"participants": [sender_id, recipient_id]}
        mock_conv_ref.get.return_value = mock_conv_doc

        mock_msg_ref = MagicMock()
        mock_conv_ref.collection.return_value.document.return_value = mock_msg_ref
        mock_msg_ref.id = "msg789"

        # Execute
        msg_id = MessagingRepository.add_message(self.mock_db, conv_id, message_data)

        # Verify
        assert msg_id == "msg789"

        # Verify batch set for message
        self.mock_batch.set.assert_called_once()
        set_args = self.mock_batch.set.call_args[0]
        assert set_args[0] == mock_msg_ref
        assert set_args[1]["senderId"] == sender_id
        assert set_args[1]["content"] == "Hello"

        # Verify batch update for conversation
        self.mock_batch.update.assert_called_once()
        update_args = self.mock_batch.update.call_args[0]
        assert update_args[0] == mock_conv_ref
        updates = update_args[1]
        assert updates["lastMessage"] == "Hello"
        assert updates["lastMessageSenderId"] == sender_id
        assert f"unreadCount.{recipient_id}" in updates

    def test_mark_as_read(self) -> None:
        conv_id = "conv123"
        user_id = "user1"

        mock_conv_ref = MagicMock()
        self.mock_db.collection.return_value.document.return_value = mock_conv_ref

        MessagingRepository.mark_as_read(self.mock_db, conv_id, user_id)

        mock_conv_ref.update.assert_called_once_with({f"unreadCount.{user_id}": 0})


if __name__ == "__main__":
    unittest.main()
