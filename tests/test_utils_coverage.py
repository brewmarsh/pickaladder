from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from pickaladder.group.utils import (
    friend_group_members,
    get_group_leaderboard,
    get_leaderboard_trend_data,
    get_random_joke,
    get_user_group_stats,
    send_invite_email_background,
)


class TestUtilsCoverage(unittest.TestCase):
    def test_get_random_joke(self) -> None:
        joke = get_random_joke()
        self.assertIsInstance(joke, str)
        self.assertGreater(len(joke), 0)

    @patch("pickaladder.group.utils.firestore")
    def test_get_group_leaderboard_doubles(self, mock_firestore: MagicMock) -> None:
        mock_db = mock_firestore.client.return_value
        mock_group_doc = MagicMock()
        mock_group_doc.exists = True

        mock_user1_ref = MagicMock()
        mock_user1_ref.id = "user1"
        mock_user2_ref = MagicMock()
        mock_user2_ref.id = "user2"
        mock_user3_ref = MagicMock()
        mock_user3_ref.id = "user3"
        mock_user4_ref = MagicMock()
        mock_user4_ref.id = "user4"
        member_refs = [mock_user1_ref, mock_user2_ref, mock_user3_ref, mock_user4_ref]

        for ref in member_refs:
            user_doc = MagicMock()
            user_doc.exists = True
            user_doc.to_dict.return_value = {"name": ref.id}
            ref.get.return_value = user_doc

        mock_group_doc.to_dict.return_value = {"members": member_refs}
        mock_db.collection("groups").document(
            "group1"
        ).get.return_value = mock_group_doc

        mock_match = MagicMock()
        mock_match.to_dict.return_value = {
            "matchType": "doubles",
            "team1": [mock_user1_ref, mock_user2_ref],
            "team2": [mock_user3_ref, mock_user4_ref],
            "player1Score": 11,
            "player2Score": 5,
            "matchDate": datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        }
        mock_db.collection("matches").where.return_value.stream.return_value = [
            mock_match
        ]

        leaderboard = get_group_leaderboard("group1")

        self.assertEqual(len(leaderboard), 4)
        player1_stats = next(p for p in leaderboard if p["id"] == "user1")
        player2_stats = next(p for p in leaderboard if p["id"] == "user2")
        player3_stats = next(p for p in leaderboard if p["id"] == "user3")
        player4_stats = next(p for p in leaderboard if p["id"] == "user4")

        self.assertEqual(player1_stats["wins"], 1)
        self.assertEqual(player1_stats["losses"], 0)
        self.assertEqual(player1_stats["avg_score"], 11)
        self.assertEqual(player2_stats["wins"], 1)
        self.assertEqual(player2_stats["losses"], 0)
        self.assertEqual(player2_stats["avg_score"], 11)
        self.assertEqual(player3_stats["wins"], 0)
        self.assertEqual(player3_stats["losses"], 1)
        self.assertEqual(player3_stats["avg_score"], 5)
        self.assertEqual(player4_stats["wins"], 0)
        self.assertEqual(player4_stats["losses"], 1)
        self.assertEqual(player4_stats["avg_score"], 5)

    @patch("pickaladder.group.utils.firestore")
    def test_get_group_leaderboard_draw(self, mock_firestore: MagicMock) -> None:
        mock_db = mock_firestore.client.return_value
        mock_group_doc = MagicMock()
        mock_group_doc.exists = True

        mock_user1_ref = MagicMock()
        mock_user1_ref.id = "user1"
        mock_user2_ref = MagicMock()
        mock_user2_ref.id = "user2"
        member_refs = [mock_user1_ref, mock_user2_ref]

        for ref in member_refs:
            user_doc = MagicMock()
            user_doc.exists = True
            user_doc.to_dict.return_value = {"name": ref.id}
            ref.get.return_value = user_doc

        mock_group_doc.to_dict.return_value = {"members": member_refs}
        mock_db.collection("groups").document(
            "group1"
        ).get.return_value = mock_group_doc

        mock_match = MagicMock()
        mock_match.to_dict.return_value = {
            "matchType": "singles",
            "player1Ref": mock_user1_ref,
            "player2Ref": mock_user2_ref,
            "player1Score": 10,
            "player2Score": 10,
            "matchDate": datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        }
        mock_db.collection("matches").where.return_value.stream.return_value = [
            mock_match
        ]

        leaderboard = get_group_leaderboard("group1")

        self.assertEqual(len(leaderboard), 2)
        player1_stats = next(p for p in leaderboard if p["id"] == "user1")
        player2_stats = next(p for p in leaderboard if p["id"] == "user2")

        self.assertEqual(player1_stats["wins"], 0)
        self.assertEqual(player1_stats["losses"], 0)
        self.assertEqual(player1_stats["games_played"], 1)
        self.assertEqual(player2_stats["wins"], 0)
        self.assertEqual(player2_stats["losses"], 0)
        self.assertEqual(player2_stats["games_played"], 1)

    @patch("pickaladder.group.utils.firestore")
    def test_get_group_leaderboard_no_members(self, mock_firestore: MagicMock) -> None:
        mock_db = mock_firestore.client.return_value
        mock_group_doc = MagicMock()
        mock_group_doc.exists = True
        mock_group_doc.to_dict.return_value = {"members": []}
        mock_db.collection("groups").document(
            "group1"
        ).get.return_value = mock_group_doc

        leaderboard = get_group_leaderboard("group1")
        self.assertEqual(leaderboard, [])

    @patch("pickaladder.group.utils.firestore")
    def test_get_group_leaderboard_no_matches(self, mock_firestore: MagicMock) -> None:
        mock_db = mock_firestore.client.return_value
        mock_group_doc = MagicMock()
        mock_group_doc.exists = True

        mock_user1_ref = MagicMock()
        mock_user1_ref.id = "user1"
        mock_user2_ref = MagicMock()
        mock_user2_ref.id = "user2"
        member_refs = [mock_user1_ref, mock_user2_ref]

        for ref in member_refs:
            user_doc = MagicMock()
            user_doc.exists = True
            user_doc.to_dict.return_value = {"name": ref.id}
            ref.get.return_value = user_doc

        mock_group_doc.to_dict.return_value = {"members": member_refs}
        mock_db.collection("groups").document(
            "group1"
        ).get.return_value = mock_group_doc
        mock_db.collection("matches").where.return_value.stream.return_value = []

        leaderboard = get_group_leaderboard("group1")

        self.assertEqual(len(leaderboard), 2)
        player1_stats = next(p for p in leaderboard if p["id"] == "user1")
        player2_stats = next(p for p in leaderboard if p["id"] == "user2")

        self.assertEqual(player1_stats["wins"], 0)
        self.assertEqual(player1_stats["losses"], 0)
        self.assertEqual(player1_stats["games_played"], 0)
        self.assertEqual(player2_stats["wins"], 0)
        self.assertEqual(player2_stats["losses"], 0)
        self.assertEqual(player2_stats["games_played"], 0)

    @patch("pickaladder.group.utils.datetime")
    @patch("pickaladder.group.utils.firestore")
    def test_get_group_leaderboard_rank_change(
        self, mock_firestore: MagicMock, mock_datetime: MagicMock
    ) -> None:
        mock_db = mock_firestore.client.return_value
        mock_group_doc = MagicMock()
        mock_group_doc.exists = True

        mock_user1_ref = MagicMock()
        mock_user1_ref.id = "user1"
        mock_user2_ref = MagicMock()
        mock_user2_ref.id = "user2"
        member_refs = [mock_user1_ref, mock_user2_ref]

        for ref in member_refs:
            user_doc = MagicMock()
            user_doc.exists = True
            user_doc.to_dict.return_value = {"name": ref.id}
            ref.get.return_value = user_doc

        mock_group_doc.to_dict.return_value = {"members": member_refs}
        mock_db.collection("groups").document(
            "group1"
        ).get.return_value = mock_group_doc

        now = datetime.now(timezone.utc)
        mock_datetime.now.return_value = now
        one_week_ago = now - timedelta(days=7)
        two_weeks_ago = now - timedelta(days=14)

        mock_match_last_week = MagicMock()
        mock_match_last_week.to_dict.return_value = {
            "matchType": "singles",
            "player1Ref": mock_user1_ref,
            "player2Ref": mock_user2_ref,
            "player1Score": 5,
            "player2Score": 11,
            "matchDate": two_weeks_ago,
        }
        mock_match_this_week = MagicMock()
        mock_match_this_week.to_dict.return_value = {
            "matchType": "singles",
            "player1Ref": mock_user1_ref,
            "player2Ref": mock_user2_ref,
            "player1Score": 11,
            "player2Score": 5,
            "matchDate": one_week_ago,
        }
        mock_db.collection("matches").where.return_value.stream.return_value = [
            mock_match_last_week,
            mock_match_this_week,
        ]

        leaderboard = get_group_leaderboard("group1")

        self.assertEqual(len(leaderboard), 2)
        player1_stats = next(p for p in leaderboard if p["id"] == "user1")
        player2_stats = next(p for p in leaderboard if p["id"] == "user2")

        self.assertEqual(player1_stats["rank_change"], 1)  # Was 2nd, now 1st
        self.assertEqual(player2_stats["rank_change"], -1)  # Was 1st, now 2nd

    @patch("pickaladder.group.utils.firestore")
    def test_get_group_leaderboard_winning_streak(
        self, mock_firestore: MagicMock
    ) -> None:
        mock_db = mock_firestore.client.return_value
        mock_group_doc = MagicMock()
        mock_group_doc.exists = True

        mock_user1_ref = MagicMock()
        mock_user1_ref.id = "user1"
        mock_user2_ref = MagicMock()
        mock_user2_ref.id = "user2"
        member_refs = [mock_user1_ref, mock_user2_ref]

        for ref in member_refs:
            user_doc = MagicMock()
            user_doc.exists = True
            user_doc.to_dict.return_value = {"name": ref.id}
            ref.get.return_value = user_doc

        mock_group_doc.to_dict.return_value = {"members": member_refs}
        mock_db.collection("groups").document(
            "group1"
        ).get.return_value = mock_group_doc

        now = datetime.now(timezone.utc)
        matches = []
        for i in range(5):
            match = MagicMock()
            match.to_dict.return_value = {
                "matchType": "singles",
                "player1Ref": mock_user1_ref,
                "player2Ref": mock_user2_ref,
                "player1Score": 11,
                "player2Score": 5,
                "matchDate": now - timedelta(days=i),
            }
            matches.append(match)

        mock_db.collection("matches").where.return_value.stream.return_value = matches

        leaderboard = get_group_leaderboard("group1")
        player1_stats = next(p for p in leaderboard if p["id"] == "user1")
        self.assertEqual(player1_stats["streak"], 5)
        self.assertTrue(player1_stats["is_on_fire"])

    @patch("pickaladder.group.utils.firestore")
    def test_get_leaderboard_trend_data_no_matches(
        self, mock_firestore: MagicMock
    ) -> None:
        mock_db = mock_firestore.client.return_value
        mock_db.collection("matches").where.return_value.stream.return_value = []

        trend_data = get_leaderboard_trend_data("group1")

        self.assertEqual(trend_data["labels"], [])
        self.assertEqual(trend_data["datasets"], [])

    @patch("pickaladder.group.utils.firestore")
    def test_get_leaderboard_trend_data_with_matches(
        self, mock_firestore: MagicMock
    ) -> None:
        mock_db = mock_firestore.client.return_value

        mock_user1_ref = MagicMock()
        mock_user1_ref.id = "user1"
        mock_user2_ref = MagicMock()
        mock_user2_ref.id = "user2"

        mock_user1_ref.get.return_value.to_dict.return_value = {"name": "User 1"}
        mock_user2_ref.get.return_value.to_dict.return_value = {"name": "User 2"}

        mock_match1 = MagicMock()
        mock_match1.to_dict.return_value = {
            "matchType": "singles",
            "player1Ref": mock_user1_ref,
            "player2Ref": mock_user2_ref,
            "player1Score": 11,
            "player2Score": 5,
            "matchDate": datetime(2023, 1, 1),
        }
        mock_match2 = MagicMock()
        mock_match2.to_dict.return_value = {
            "matchType": "singles",
            "player1Ref": mock_user1_ref,
            "player2Ref": mock_user2_ref,
            "player1Score": 5,
            "player2Score": 11,
            "matchDate": datetime(2023, 1, 2),
        }
        mock_db.collection("matches").where.return_value.stream.return_value = [
            mock_match1,
            mock_match2,
        ]

        mock_user1_doc = MagicMock()
        mock_user1_doc.id = "user1"
        mock_user1_doc.exists = True
        mock_user1_doc.to_dict.return_value = {"name": "User 1"}
        mock_user2_doc = MagicMock()
        mock_user2_doc.id = "user2"
        mock_user2_doc.exists = True
        mock_user2_doc.to_dict.return_value = {"name": "User 2"}
        mock_db.get_all.return_value = [mock_user1_doc, mock_user2_doc]

        trend_data = get_leaderboard_trend_data("group1")

        self.assertEqual(trend_data["labels"], ["2023-01-01", "2023-01-02"])
        self.assertEqual(len(trend_data["datasets"]), 2)

        user1_data = next(
            ds for ds in trend_data["datasets"] if ds["label"] == "User 1"
        )
        user2_data = next(
            ds for ds in trend_data["datasets"] if ds["label"] == "User 2"
        )

        self.assertEqual(user1_data["data"], [11.0, 8.0])
        self.assertEqual(user2_data["data"], [5.0, 8.0])

    @patch("pickaladder.group.utils.get_group_leaderboard")
    @patch("pickaladder.group.utils.firestore")
    def test_get_user_group_stats(
        self, mock_firestore: MagicMock, mock_get_group_leaderboard: MagicMock
    ) -> None:
        mock_db = mock_firestore.client.return_value
        mock_get_group_leaderboard.return_value = [
            {"id": "user1", "wins": 10, "losses": 5},
            {"id": "user2", "wins": 5, "losses": 10},
        ]

        now = datetime.now()
        mock_user1_ref = mock_db.collection("users").document("user1")
        mock_user2_ref = mock_db.collection("users").document("user2")

        matches = []
        for i in range(3):
            match = MagicMock()
            match.to_dict.return_value = {
                "matchType": "singles",
                "player1Ref": mock_user1_ref,
                "player2Ref": mock_user2_ref,
                "player1Score": 11,
                "player2Score": 5,
                "matchDate": now - timedelta(days=i),
            }
            matches.append(match)

        mock_db.collection("matches").where.return_value.stream.return_value = matches

        stats = get_user_group_stats("group1", "user1")

        self.assertEqual(stats["rank"], 1)
        self.assertEqual(stats["wins"], 10)
        self.assertEqual(stats["losses"], 5)
        self.assertEqual(stats["win_streak"], 3)
        self.assertEqual(stats["longest_streak"], 3)

    @patch("pickaladder.group.utils.get_group_leaderboard")
    @patch("pickaladder.group.utils.firestore")
    def test_get_user_group_stats_invalid_user(
        self, mock_firestore: MagicMock, mock_get_group_leaderboard: MagicMock
    ) -> None:
        mock_get_group_leaderboard.return_value = [
            {"id": "user1", "wins": 10, "losses": 5}
        ]
        mock_db = mock_firestore.client.return_value
        mock_db.collection("matches").where.return_value.stream.return_value = []

        stats = get_user_group_stats("group1", "invalid_user")

        self.assertEqual(stats["rank"], "N/A")
        self.assertEqual(stats["wins"], 0)
        self.assertEqual(stats["losses"], 0)
        self.assertEqual(stats["win_streak"], 0)
        self.assertEqual(stats["longest_streak"], 0)

    def test_friend_group_members(self) -> None:
        mock_db = MagicMock()
        mock_group_doc = MagicMock()
        mock_group_doc.exists = True

        mock_user1_ref = MagicMock()
        mock_user1_ref.id = "user1"
        mock_user2_ref = MagicMock()
        mock_user2_ref.id = "user2"
        new_member_ref = MagicMock()
        new_member_ref.id = "new_member"

        member_refs = [mock_user1_ref, mock_user2_ref, new_member_ref]
        mock_group_doc.to_dict.return_value = {"members": member_refs}
        mock_db.collection("groups").document(
            "group1"
        ).get.return_value = mock_group_doc

        mock_batch = MagicMock()
        mock_db.batch.return_value = mock_batch

        friend_group_members(mock_db, "group1", new_member_ref)

        self.assertEqual(mock_batch.set.call_count, 4)
        mock_batch.commit.assert_called_once()

    @patch("pickaladder.group.utils.threading.Thread")
    @patch("pickaladder.group.utils.send_email")
    @patch("pickaladder.group.utils.firestore")
    def test_send_invite_email_background_success(
        self,
        mock_firestore: MagicMock,
        mock_send_email: MagicMock,
        mock_thread: MagicMock,
    ) -> None:
        mock_app = MagicMock()
        mock_app.app_context.return_value.__enter__.return_value = None
        mock_app.app_context.return_value.__exit__.return_value = None

        email_data = {"to": "test@example.com", "subject": "Test", "body": "Test"}

        # Make the thread run synchronously
        thread = MagicMock()

        def run_thread_success() -> None:
            mock_thread.call_args[1]["target"]()

        thread.start.side_effect = run_thread_success
        mock_thread.return_value = thread

        send_invite_email_background(mock_app, "invite_token", email_data)

        mock_send_email.assert_called_once_with(**email_data)
        mock_firestore.client.return_value.collection(
            "group_invites"
        ).document.return_value.update.assert_called_once_with(
            {"status": "sent", "last_error": mock_firestore.DELETE_FIELD}
        )

    @patch("pickaladder.group.utils.threading.Thread")
    @patch("pickaladder.group.utils.send_email")
    @patch("pickaladder.group.utils.firestore")
    def test_send_invite_email_background_failure(
        self,
        mock_firestore: MagicMock,
        mock_send_email: MagicMock,
        mock_thread: MagicMock,
    ) -> None:
        mock_app = MagicMock()
        mock_app.app_context.return_value.__enter__.return_value = None
        mock_app.app_context.return_value.__exit__.return_value = None

        email_data = {"to": "test@example.com", "subject": "Test", "body": "Test"}
        mock_send_email.side_effect = Exception("Email failed")

        # Make the thread run synchronously
        thread = MagicMock()

        def run_thread_failure() -> None:
            mock_thread.call_args[1]["target"]()

        thread.start.side_effect = run_thread_failure
        mock_thread.return_value = thread

        send_invite_email_background(mock_app, "invite_token", email_data)

        mock_send_email.assert_called_once_with(**email_data)
        mock_firestore.client.return_value.collection(
            "group_invites"
        ).document.return_value.update.assert_called_once_with(
            {"status": "failed", "last_error": "Email failed"}
        )


if __name__ == "__main__":
    unittest.main()
