from __future__ import annotations

import unittest
from typing import cast

from pickaladder.user.helpers import smart_display_name
from pickaladder.utils import mask_email


class TestGhostDisplay(unittest.TestCase):
    def test_mask_email(self) -> None:
        assert mask_email("march@gmail.com") == "m...h@gmail.com"
        assert mask_email("a@gmail.com") == "a...@gmail.com"
        assert mask_email("me@gmail.com") == "m...e@gmail.com"
        assert mask_email("") == ""
        # Using cast to test None handling without violating mask_email's str type hint
        assert mask_email(cast("str", None)) is None
        assert mask_email("invalid-email") == "invalid-email"

    def test_smart_display_name_ghost_with_email(self) -> None:
        user = {
            "username": "ghost_ceec6a",
            "email": "march@gmail.com",
            "name": "John Doe",
        }
        # implementation prioritizes name
        assert smart_display_name(user) == "John Doe"

    def test_smart_display_name_ghost_no_email_no_name(self) -> None:
        user = {"username": "ghost_ceec6a"}
        assert smart_display_name(user) == "Guest Player"

    def test_smart_display_name_ghost_no_email_with_name(self) -> None:
        user = {"username": "ghost_ceec6a", "name": "John Doe"}
        # implementation prioritizes name
        assert smart_display_name(user) == "John Doe"

    def test_smart_display_name_regular_user(self) -> None:
        user = {"username": "jdoe", "email": "jdoe@example.com", "name": "John Doe"}
        # Now prioritizes name over username
        assert smart_display_name(user) == "John Doe"


if __name__ == "__main__":
    unittest.main()
