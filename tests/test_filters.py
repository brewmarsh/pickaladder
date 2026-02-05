from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from pickaladder import create_app


class TestFilters(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "WTF_CSRF_ENABLED": False})
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    def test_display_name_filter_registration(self):
        """Test that display_name filter is registered."""
        self.assertIn("display_name", self.app.jinja_env.filters)

    def test_display_name_filter_logic(self):
        """Test the logic of the display_name filter."""
        display_name_filter = self.app.jinja_env.filters["display_name"]

        # Test regular user
        user = {"username": "jdoe", "name": "John Doe"}
        self.assertEqual(display_name_filter(user), "jdoe")

        # Test ghost user with email
        ghost_user = {
            "username": "ghost_123",
            "email": "test@example.com",
            "name": "Test User"
        }
        # m...l@domain.com logic from mask_email
        # t...t@example.com
        self.assertEqual(display_name_filter(ghost_user), "t...t@example.com")

        # Test ghost user without email or name
        ghost_user_minimal = {"username": "ghost_123"}
        self.assertEqual(display_name_filter(ghost_user_minimal), "Pending Invite")

if __name__ == "__main__":
    unittest.main()
