from __future__ import annotations

import unittest
from typing import cast

from pickaladder.user.services import UserService
from pickaladder.utils import mask_email


class TestGhostDisplay(unittest.TestCase):
    def test_mask_email(self) -> None:
        self.assertEqual(mask_email("march@gmail.com"), "m...h@gmail.com")
        self.assertEqual(mask_email("a@gmail.com"), "a...@gmail.com")
        self.assertEqual(mask_email("me@gmail.com"), "m...e@gmail.com")
        self.assertEqual(mask_email(""), "")
        # Using cast to test None handling without violating mask_email's str type hint
        self.assertEqual(mask_email(cast(str, None)), None)
        self.assertEqual(mask_email("invalid-email"), "invalid-email")

    def test_smart_display_name_ghost_with_email(self) -> None:
        user = {
            "username": "ghost_ceec6a",
            "email": "march@gmail.com",
            "name": "John Doe",
        }
        # Prioritizes name over email for ghosts
        self.assertEqual(UserService.smart_display_name(user), "John Doe")

    def test_smart_display_name_ghost_no_email_no_name(self) -> None:
        user = {"username": "ghost_ceec6a"}
        self.assertEqual(UserService.smart_display_name(user), "Pending Invite")

    def test_smart_display_name_ghost_no_email_with_name(self) -> None:
        user = {"username": "ghost_ceec6a", "name": "John Doe"}
        # Prioritizes name for ghosts
        self.assertEqual(UserService.smart_display_name(user), "John Doe")

    def test_smart_display_name_regular_user(self) -> None:
        user = {"username": "jdoe", "email": "jdoe@example.com", "name": "John Doe"}
        self.assertEqual(UserService.smart_display_name(user), "jdoe")


if __name__ == "__main__":
    unittest.main()