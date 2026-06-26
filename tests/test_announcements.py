"""Tests for group announcements."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from pickaladder.messaging.repository import MessagingRepository
from pickaladder.messaging.services import MessagingService


class AnnouncementTestCase(unittest.TestCase):
    """Test cases for group announcements logic."""

    def setUp(self) -> None:
        self.mock_db = MagicMock()

    @patch("pickaladder.messaging.repository.MessagingRepository.create")
    @patch(
        "pickaladder.messaging.repository.MessagingRepository.find_direct_conversation",
    )  # Not exactly find_direct, but we'll see
    def test_get_or_create_group_announcement_new(self, mock_find, mock_create) -> None:
        """Test creating a new announcement channel."""
        # Assume we use a query to find group_announcements.

        # Mocking query in MessagingService.get_or_create_group_announcement
        coll = self.mock_db.collection.return_value
        q = coll.where.return_value.where.return_value
        mock_query = q.limit.return_value.stream
        mock_query.return_value = []  # Not found

        mock_create.return_value = "ann_conv_id"

        cid = MessagingService.get_or_create_group_announcement(
            self.mock_db,
            "group1",
            "owner1",
            ["owner1", "m1", "m2"],
        )

        assert cid == "ann_conv_id"
        mock_create.assert_called_once()
        payload = mock_create.call_args[0][1]
        assert payload["type"] == "group_announcement"
        assert payload["groupId"] == "group1"
        assert payload["ownerId"] == "owner1"
        assert "m1" in payload["participants"]
        assert payload["unreadCount"]["m1"] == 0

    @patch(
        "pickaladder.messaging.repository.MessagingRepository.get_user_conversations",
    )
    @patch("pickaladder.group.repository.GroupRepository.get_by_id")
    @patch("pickaladder.user.services.UserService.get_user_by_id")
    def test_get_inbox_with_announcements(
        self,
        mock_get_user,
        mock_get_group,
        mock_get_convs,
    ) -> None:
        """Test inbox display for announcements."""
        mock_get_convs.return_value = [
            {
                "id": "ann1",
                "type": "group_announcement",
                "groupId": "group1",
                "participants": ["u1", "u2"],
                "unreadCount": {"u1": 1},
            },
        ]
        mock_get_group.return_value = {"name": "Test Group"}

        inbox = MessagingService.get_inbox(self.mock_db, "u1")

        assert len(inbox) == 1
        assert inbox[0]["display_name"] == "Test Group (Announcements)"

    @patch("pickaladder.messaging.repository.firestore.Increment")
    def test_add_message_multi_unread(self, mock_increment) -> None:
        """Test that multiple participants get unread increments."""
        # This tests MessagingRepository.add_message
        mock_conv_ref = self.mock_db.collection.return_value.document.return_value
        mock_conv_doc = mock_conv_ref.get.return_value
        mock_conv_doc.exists = True
        mock_conv_doc.to_dict.return_value = {"participants": ["sender", "m1", "m2"]}

        mock_batch = self.mock_db.batch.return_value

        msg_data = {"senderId": "sender", "content": "Hello"}
        MessagingRepository.add_message(self.mock_db, "conv1", msg_data)

        # Verify batch.update was called with unreadCount increments for m1 and m2
        updates = mock_batch.update.call_args[0][1]
        assert "unreadCount.m1" in updates
        assert "unreadCount.m2" in updates
        assert "unreadCount.sender" not in updates


if __name__ == "__main__":
    unittest.main()
