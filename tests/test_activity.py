"""Tests for the social activity service."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from pickaladder.core.activity.services import ActivityService


class ActivityServiceTestCase(unittest.TestCase):
    """Test cases for the ActivityService."""

    def setUp(self):
        self.mock_db = MagicMock()

    def test_log_activity(self):
        """Test recording a community event."""
        # Directly call the static method to bypass any class-level patching issues
        from pickaladder.core.activity.services import ActivityService as OrigService

        mock_coll = self.mock_db.collection.return_value
        mock_doc = mock_coll.document.return_value
        mock_doc.id = "act123"

        act_id = OrigService.log_activity(
            self.mock_db, "user1", "MATCH_COMPLETED", {"score": "11-5"}
        )

        self.assertEqual(act_id, "act123")
        mock_doc.set.assert_called_once()
        args = mock_doc.set.call_args[0][0]
        self.assertEqual(args["userId"], "user1")
        self.assertEqual(args["type"], "MATCH_COMPLETED")

    def test_toggle_reaction_add(self):
        """Test adding a reaction to an activity."""
        mock_ref = self.mock_db.collection.return_value.document.return_value
        mock_doc = mock_ref.get.return_value
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"reactions": []}

        reactions = ActivityService.toggle_reaction(self.mock_db, "act1", "user1")

        self.assertEqual(len(reactions), 1)
        self.assertEqual(reactions[0]["userId"], "user1")
        mock_ref.update.assert_called_once()

    def test_toggle_reaction_remove(self):
        """Test removing an existing reaction."""
        mock_ref = self.mock_db.collection.return_value.document.return_value
        mock_doc = mock_ref.get.return_value
        mock_doc.exists = True
        # User1 already has a reaction
        mock_doc.to_dict.return_value = {
            "reactions": [{"userId": "user1", "type": "CHEER"}]
        }

        reactions = ActivityService.toggle_reaction(self.mock_db, "act1", "user1")

        self.assertEqual(len(reactions), 0)
        mock_ref.update.assert_called_once()


if __name__ == "__main__":
    unittest.main()
