"""Tests for the messaging service."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from pickaladder.messaging.services import MessagingService


class MessagingServiceTestCase(unittest.TestCase):
    """Test cases for the MessagingService."""

    def setUp(self):
        self.mock_db = MagicMock()

    @patch("pickaladder.messaging.services.MessagingRepository")
    def test_get_or_create_conversation_existing(self, mock_repo):
        """Test retrieving an existing conversation."""
        mock_repo.find_direct_conversation.return_value = {"id": "conv123"}

        cid = MessagingService.get_or_create_conversation(self.mock_db, "u1", "u2")

        self.assertEqual(cid, "conv123")
        mock_repo.create.assert_not_called()

    @patch("pickaladder.messaging.services.MessagingRepository")
    def test_get_or_create_conversation_new(self, mock_repo):
        """Test creating a new conversation."""
        mock_repo.find_direct_conversation.return_value = None
        mock_repo.create.return_value = "new_conv"

        cid = MessagingService.get_or_create_conversation(self.mock_db, "u1", "u2")

        self.assertEqual(cid, "new_conv")
        mock_repo.create.assert_called_once()

    @patch("pickaladder.messaging.services.MessagingRepository")
    def test_send_message(self, mock_repo):
        """Test sending a message."""
        mock_repo.add_message.return_value = "msg1"

        mid = MessagingService.send_message(self.mock_db, "conv1", "u1", "Hello")

        self.assertEqual(mid, "msg1")
        mock_repo.add_message.assert_called_once()
        args = mock_repo.add_message.call_args[0][2]
        self.assertEqual(args["content"], "Hello")
        self.assertEqual(args["senderId"], "u1")

if __name__ == "__main__":
    unittest.main()
