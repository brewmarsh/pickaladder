"""Tests for the rising stars logic."""

from __future__ import annotations

import datetime
import unittest
from unittest.mock import MagicMock, patch

from pickaladder.match.services import MatchRecordService


class TestRisingStars(unittest.TestCase):
    """Test case for the rising stars logic."""

    def test_get_rising_stars_with_datetime(self) -> None:
        """Test that get_rising_stars correctly handles datetime and aggregates wins."""
        mock_db = MagicMock()

        # Setup mock user docs
        user1_doc = MagicMock()
        user1_doc.exists = True
        user1_doc.to_dict.return_value = {"username": "star1", "name": "Star One"}

        user2_doc = MagicMock()
        user2_doc.exists = True
        user2_doc.to_dict.return_value = {"username": "star2", "name": "Star Two"}

        def document_side_effect(uid: str) -> MagicMock:
            if uid == "u1":
                return user1_doc
            if uid == "u2":
                return user2_doc
            return MagicMock(exists=False)

        mock_db.collection.return_value.document.side_effect = document_side_effect

        # Setup mock matches
        now = datetime.datetime.now(datetime.timezone.utc)

        match1 = MagicMock()
        match1.to_dict.return_value = {
            "winnerId": "u1",
            "matchDate": now - datetime.timedelta(days=1),
        }

        match2 = MagicMock()
        match2.to_dict.return_value = {
            "winnerId": "u1",
            "matchDate": now - datetime.timedelta(days=2),
        }

        match3 = MagicMock()
        match3.to_dict.return_value = {
            "winnerId": "u2",
            "matchDate": now - datetime.timedelta(days=3),
        }

        # This match is too old
        match4 = MagicMock()
        match4.to_dict.return_value = {
            "winnerId": "u2",
            "matchDate": now - datetime.timedelta(days=10),
        }

        # Mock query.stream()
        # In mockfirestore, the query is chained.
        # db.collection("matches").where(...).stream()
        mock_db.collection.return_value.where.return_value.stream.return_value = [
            match1,
            match2,
            match3,
        ]

        # Running the function
        stars = MatchRecordService.get_rising_stars(mock_db, limit=2)

        # Assertions
        self.assertEqual(len(stars), 2)
        self.assertEqual(stars[0]["id"], "u1")
        self.assertEqual(stars[0]["weekly_wins"], 2)
        self.assertEqual(stars[1]["id"], "u2")
        self.assertEqual(stars[1]["weekly_wins"], 1)

    @patch("firebase_admin.firestore.FieldFilter")
    def test_get_rising_stars_type_error_prevention(
        self, mock_field_filter: MagicMock
    ) -> None:
        """Test that the query is constructed with a datetime object."""
        mock_db = MagicMock()
        mock_db.collection.return_value.where.return_value.stream.return_value = []

        MatchRecordService.get_rising_stars(mock_db)

        # Check that FieldFilter was called with a datetime object
        args, kwargs = mock_field_filter.call_args
        self.assertEqual(args[0], "matchDate")
        self.assertEqual(args[1], ">=")
        self.assertIsInstance(args[2], datetime.datetime)


if __name__ == "__main__":
    unittest.main()
