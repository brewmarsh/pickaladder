"""Tests for dashboard tournament fetching."""

from __future__ import annotations

import datetime
import unittest
from unittest.mock import MagicMock, patch

from pickaladder.user.services import UserService


class DashboardTournamentsTestCase(unittest.TestCase):
    """Test case for fetching dashboard tournaments."""

    def test_get_active_tournaments(self) -> None:
        """Test getting active tournaments."""
        user_id = "user123"
        mock_db = MagicMock()

        # Mock tournament documents
        mock_doc1 = MagicMock()
        mock_doc1.id = "t1"
        mock_doc1.to_dict.return_value = {
            "name": "Active Tournament",
            "status": "Active",
            "participant_ids": [user_id],
            "participants": [{"user_id": user_id, "status": "accepted"}],
            "date": datetime.datetime(2023, 10, 1),
        }

        mock_doc2 = MagicMock()
        mock_doc2.id = "t2"
        mock_doc2.to_dict.return_value = {
            "name": "Scheduled Tournament",
            "status": "Scheduled",
            "participant_ids": [user_id],
            "participants": [{"user_id": user_id, "status": "accepted"}],
            "date": datetime.datetime(2023, 11, 1),
        }

        mock_doc3 = MagicMock()
        mock_doc3.id = "t3"
        mock_doc3.to_dict.return_value = {
            "name": "Pending Tournament",
            "status": "Active",
            "participant_ids": [user_id],
            "participants": [{"user_id": user_id, "status": "pending"}],
            "date": datetime.datetime(2023, 10, 1),
        }

        mock_db.collection.return_value.where.return_value.stream.return_value = [
            mock_doc1,
            mock_doc2,
            mock_doc3,
        ]

        active = UserService.get_active_tournaments(mock_db, user_id)

        self.assertEqual(len(active), 2)
        self.assertEqual(active[0]["name"], "Active Tournament")
        self.assertEqual(active[1]["name"], "Scheduled Tournament")
        self.assertIn("date_display", active[0])

    def test_get_active_tournaments_sorting(self) -> None:
        """Test that active tournaments are sorted by date ascending."""
        user_id = "user123"
        mock_db = MagicMock()

        mock_doc1 = MagicMock()
        mock_doc1.id = "t1"
        mock_doc1.to_dict.return_value = {
            "name": "Later Tournament",
            "status": "Active",
            "participant_ids": [user_id],
            "participants": [{"user_id": user_id, "status": "accepted"}],
            "date": datetime.datetime(2023, 12, 1),
        }

        mock_doc2 = MagicMock()
        mock_doc2.id = "t2"
        mock_doc2.to_dict.return_value = {
            "name": "Earlier Tournament",
            "status": "Active",
            "participant_ids": [user_id],
            "participants": [{"user_id": user_id, "status": "accepted"}],
            "date": datetime.datetime(2023, 11, 1),
        }

        mock_db.collection.return_value.where.return_value.stream.return_value = [
            mock_doc1,
            mock_doc2,
        ]

        active = UserService.get_active_tournaments(mock_db, user_id)

        self.assertEqual(len(active), 2)
        self.assertEqual(active[0]["name"], "Earlier Tournament")
        self.assertEqual(active[1]["name"], "Later Tournament")

    def test_get_past_tournaments(self) -> None:
        """Test getting past tournaments."""
        user_id = "user123"
        mock_db = MagicMock()

        # Mock tournament documents
        mock_doc = MagicMock()
        mock_doc.id = "t_past"
        mock_doc.to_dict.return_value = {
            "name": "Past Tournament",
            "status": "Completed",
            "participant_ids": [user_id],
            "matchType": "singles",
            "date": datetime.datetime(2023, 1, 1),
        }

        mock_db.collection.return_value.where.return_value.stream.return_value = [
            mock_doc
        ]

        # Mock get_tournament_standings
        mock_standings = [{"name": "Winner Name", "wins": 5}]
        with patch(
            "pickaladder.tournament.utils.get_tournament_standings"
        ) as mock_get_standings:
            mock_get_standings.return_value = mock_standings

            past = UserService.get_past_tournaments(mock_db, user_id)

            self.assertEqual(len(past), 1)
            self.assertEqual(past[0]["name"], "Past Tournament")
            self.assertEqual(past[0]["winner_name"], "Winner Name")
            self.assertIn("date_display", past[0])
