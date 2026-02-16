"""Tests for profile picture fix on share card."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from pickaladder import create_app
from pickaladder.group.services.leaderboard import (
    get_group_leaderboard as get_group_leaderboard_service,
)


class ProfilePictureFixTestCase(unittest.TestCase):
    """Test case for profile picture fix."""

    def setUp(self) -> None:
        self.app = create_app({"TESTING": True, "WTF_CSRF_ENABLED": False})
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self) -> None:
        self.ctx.pop()

    @patch("pickaladder.group.services.leaderboard.firestore")
    def test_leaderboard_includes_profile_picture_url(
        self, mock_firestore: MagicMock
    ) -> None:
        """Test that get_group_leaderboard includes profilePictureUrl and profilePictureThumbnailUrl."""
        mock_db = mock_firestore.client.return_value

        # Mock user data with profile picture
        user1_data = {
            "username": "user1",
            "name": "User 1",
            "profilePictureUrl": "http://example.com/pic.jpg",
            "profilePictureThumbnailUrl": "http://example.com/thumb.jpg",
        }

        mock_user1_doc = MagicMock()
        mock_user1_doc.exists = True
        mock_user1_doc.to_dict.return_value = user1_data

        mock_user1_ref = MagicMock()
        mock_user1_ref.id = "user1"
        mock_user1_ref.get.return_value = mock_user1_doc

        # Mock group data
        mock_group_doc = MagicMock()
        mock_group_doc.exists = True
        mock_group_doc.to_dict.return_value = {"members": [mock_user1_ref]}
        mock_db.collection("groups").document(
            "group1"
        ).get.return_value = mock_group_doc

        # Mock matches (empty is fine for this test as we want to check user enrichment)
        mock_db.collection("matches").where.return_value.stream.return_value = []

        # Call service version
        leaderboard = get_group_leaderboard_service("group1")
        self.assertEqual(len(leaderboard), 1)
        self.assertEqual(
            leaderboard[0]["profilePictureUrl"], "http://example.com/pic.jpg"
        )
        self.assertEqual(
            leaderboard[0]["profilePictureThumbnailUrl"], "http://example.com/thumb.jpg"
        )

    def test_avatar_url_filter_robustness(self) -> None:
        """Test that avatar_url filter handles different key names."""
        avatar_url_filter = self.app.jinja_env.filters["avatar_url"]

        # Test profilePictureUrl
        user_pp = {"username": "test", "profilePictureUrl": "http://pic.jpg"}
        self.assertEqual(avatar_url_filter(user_pp), "http://pic.jpg")

        # Test avatar_url
        user_au = {"username": "test", "avatar_url": "http://avatar.jpg"}
        self.assertEqual(avatar_url_filter(user_au), "http://avatar.jpg")

        # Test profile_picture_url
        user_p_u = {"username": "test", "profile_picture_url": "http://p_pic.jpg"}
        self.assertEqual(avatar_url_filter(user_p_u), "http://p_pic.jpg")

        # Test fallback
        user_none = {"username": "test"}
        url = avatar_url_filter(user_none)
        self.assertTrue("dicebear.com" in url)

    def test_user_session_avatar_url_robustness(self) -> None:
        """Test that UserSession.avatar_url handles different key names."""
        from pickaladder.user.models import UserSession

        # Test profilePictureUrl
        session = UserSession({"profilePictureUrl": "http://pic.jpg"})
        self.assertEqual(session.avatar_url, "http://pic.jpg")

        # Test avatar_url
        session = UserSession({"avatar_url": "http://avatar.jpg"})
        self.assertEqual(session.avatar_url, "http://avatar.jpg")

        # Test profile_picture_url
        session = UserSession({"profile_picture_url": "http://p_pic.jpg"})
        self.assertEqual(session.avatar_url, "http://p_pic.jpg")


if __name__ == "__main__":
    unittest.main()
