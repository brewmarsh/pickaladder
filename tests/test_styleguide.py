"""Tests for the Design System Styleguide."""

from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from pickaladder import create_app

# Mock user payloads
MOCK_ADMIN_ID = "admin_uid"
MOCK_ADMIN_DATA = {"name": "Admin User", "isAdmin": True}

MOCK_USER_ID = "user_uid"
MOCK_USER_DATA = {"name": "Regular User", "isAdmin": False}


class StyleguideTestCase(unittest.TestCase):
    """Test case for the design system styleguide."""

    def setUp(self) -> None:
        """Set up a test client and a comprehensive mock environment."""
        self.mock_firestore_service = MagicMock()

        patchers = {
            "init_app": patch("firebase_admin.initialize_app"),
            "firestore": patch(
                "pickaladder.admin.routes.firestore", new=self.mock_firestore_service
            ),
            "firestore_app": patch(
                "pickaladder.firestore", new=self.mock_firestore_service
            ),
            "user_firestore": patch(
                "pickaladder.user.routes.firestore", new=self.mock_firestore_service
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

    def _login_user(
        self, user_id: str, user_data: dict[str, Any], is_admin: bool
    ) -> None:
        """Simulate a user login by setting the session and mocking Firestore."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["is_admin"] = is_admin

        mock_db = self.mock_firestore_service.client.return_value
        mock_users_collection = mock_db.collection("users")

        def document_side_effect(doc_id: str) -> MagicMock:
            """Firestore document side effect mock."""
            if doc_id == user_id:
                mock_user_doc = MagicMock()
                mock_user_snapshot = MagicMock()
                mock_user_snapshot.exists = True
                mock_user_snapshot.to_dict.return_value = user_data
                mock_user_doc.get.return_value = mock_user_snapshot
                return mock_user_doc
            return MagicMock()

        mock_users_collection.document.side_effect = document_side_effect

    def test_styleguide_accessible_to_admin(self) -> None:
        """Ensure an admin user can access the styleguide."""
        self._login_user(MOCK_ADMIN_ID, MOCK_ADMIN_DATA, is_admin=True)

        response = self.client.get("/admin/styleguide")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Design System Styleguide", response.data)
        self.assertIn(b"Typography", response.data)
        self.assertIn(b"Buttons", response.data)
        self.assertIn(b"Badges", response.data)
        self.assertIn(b"Cards", response.data)
        self.assertIn(b"Hero Stats Card", response.data)

    def test_styleguide_inaccessible_to_non_admin(self) -> None:
        """Ensure a non-admin user is redirected from the styleguide."""
        self._login_user(MOCK_USER_ID, MOCK_USER_DATA, is_admin=False)

        response = self.client.get("/admin/styleguide", follow_redirects=True)
        # Depending on how @login_required(admin_required=True) is implemented,
        # it might redirect to login or show an error.
        # Based on admin() route in routes.py:
        # if not g.user or not g.user.get("isAdmin"):
        #     flash("You are not authorized to view this page.", "danger")
        #     return redirect(url_for("auth.login"))
        # Wait, the @login_required(admin_required=True) decorator should handle it.

        # Let's check auth/decorators.py
        self.assertIn(b"You are not authorized to view this page.", response.data)


if __name__ == "__main__":
    unittest.main()
