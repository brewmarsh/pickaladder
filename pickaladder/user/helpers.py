"""Helper functions for user-related data."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pickaladder.utils import mask_email

from .models import User

if TYPE_CHECKING:
    pass


def wrap_user(user_data: dict[str, Any] | None, uid: str | None = None) -> User | None:
    """Wrap a user dictionary in a User model object.

    Args:
        user_data: The user data dictionary from Firestore.
        uid: Optional user ID if not present in user_data.

    Returns:
        A User model object or None if user_data is None.
    """
    if user_data is None:
        return None
    if isinstance(user_data, User):
        return user_data

    data = dict(user_data)
    if uid:
        data["uid"] = uid
    return User(data)


