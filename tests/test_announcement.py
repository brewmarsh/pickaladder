"""Tests for the global announcement system."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from pickaladder import create_app

# Mock user payloads
MOCK_ADMIN_ID = "admin_uid"
MOCK_ADMIN_DATA = {"name": "Admin User", "isAdmin": True}


class AnnouncementTestCase(unittest.TestCase):
    """Test case for the global announcement system."""

    def setUp(self) -> None:
        """Set up a test client and a comprehensive mock environment."""
        self.mock_firestore_service = MagicMock()

        patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            "firestore_routes": patch(
                "pickaladder.admin.routes.firestore", new=self.mock_firestore_service
            ),
            "firestore_cp": patch(
                "pickaladder.context_processors.firestore",
                new=self.mock_firestore_service,
            ),
            "firestore_app": patch(
                "pickaladder.firestore", new=self.mock_firestore_service
            ),
        }

        self.mocks = {name: p.start() for name, p in patchers.items()}
        for p in patchers.values():
            self.addCleanup(p.stop)

        self.app = create_app(
            {"TESTING": True, "WTF_CSRF_ENABLED": False, "SERVER_NAME": "localhost"}
        )
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self) -> None:
        """Tear down the test client."""
        self.app_context.pop()

    def _login_admin(self) -> None:
        """Simulate an admin login."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = MOCK_ADMIN_ID
            sess["is_admin"] = True

        mock_db = self.mock_firestore_service.client.return_value
        mock_users_collection = mock_db.collection("users")
        mock_admin_doc = MagicMock()
        mock_admin_snapshot = MagicMock()
        mock_admin_snapshot.exists = True
        mock_admin_snapshot.to_dict.return_value = MOCK_ADMIN_DATA
        mock_admin_doc.get.return_value = mock_admin_snapshot
        mock_users_collection.document.return_value = mock_admin_doc

    def test_post_announcement(self) -> None:
        """Ensure an admin can update the global announcement."""
        self._login_admin()
        mock_db = self.mock_firestore_service.client.return_value
        mock_settings_doc = mock_db.collection("system").document("settings")

        response = self.client.post(
            "/admin/announcement",
            data={
                "announcement_text": "Test Announcement",
                "is_active": "on",
                "level": "warning",
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Global announcement updated successfully.", response.data)

        mock_settings_doc.set.assert_called_with(
            {
                "announcement_text": "Test Announcement",
                "is_active": True,
                "level": "warning",
            },
            merge=True,
        )

    def test_context_processor_injects_announcement(self) -> None:
        """Ensure the global announcement is injected into the template context."""
        mock_db = self.mock_firestore_service.client.return_value
        mock_settings_doc = mock_db.collection("system").document("settings")
        mock_snapshot = MagicMock()
        mock_snapshot.exists = True
        mock_snapshot.to_dict.return_value = {
            "announcement_text": "Global Message",
            "is_active": True,
            "level": "danger",
        }
        mock_settings_doc.get.return_value = mock_snapshot

        from pickaladder.context_processors import inject_global_context

        with self.app.test_request_context():
            context = inject_global_context()
            self.assertEqual(
                context["global_announcement"]["announcement_text"], "Global Message"
            )
            self.assertTrue(context["global_announcement"]["is_active"])
            self.assertEqual(context["global_announcement"]["level"], "danger")


if __name__ == "__main__":
    unittest.main()
