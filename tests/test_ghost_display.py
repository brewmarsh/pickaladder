import unittest

from pickaladder.user.utils import smart_display_name
from pickaladder.utils import mask_email


class TestGhostDisplay(unittest.TestCase):
    def test_mask_email(self):
        self.assertEqual(mask_email("march@gmail.com"), "m...h@gmail.com")
        self.assertEqual(mask_email("a@gmail.com"), "a...@gmail.com")
        self.assertEqual(mask_email("me@gmail.com"), "m...e@gmail.com")
        self.assertEqual(mask_email(""), "")
        self.assertEqual(mask_email(None), None)
        self.assertEqual(mask_email("invalid-email"), "invalid-email")

    def test_smart_display_name_ghost_with_email(self):
        user = {
            "username": "ghost_ceec6a",
            "email": "march@gmail.com",
            "name": "John Doe",
        }
        # Prioritize name over masked email
        self.assertEqual(smart_display_name(user), "John Doe")

    def test_smart_display_name_ghost_no_email_no_name(self):
        user = {"username": "ghost_ceec6a"}
        self.assertEqual(smart_display_name(user), "Pending Invite")

    def test_smart_display_name_ghost_no_email_with_name(self):
        user = {"username": "ghost_ceec6a", "name": "John Doe"}
        # Should return name if present
        self.assertEqual(smart_display_name(user), "John Doe")

    def test_smart_display_name_ghost_with_email_no_name(self):
        user = {
            "username": "ghost_ceec6a",
            "email": "march@gmail.com",
        }
        # Fallback to masked email if name is missing
        self.assertEqual(smart_display_name(user), "m...h@gmail.com")

    def test_smart_display_name_regular_user(self):
        user = {"username": "jdoe", "email": "jdoe@example.com", "name": "John Doe"}
        self.assertEqual(smart_display_name(user), "jdoe")


if __name__ == "__main__":
    unittest.main()
