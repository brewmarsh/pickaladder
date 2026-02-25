"""Data models for the group blueprint."""

from __future__ import annotations

from collections import UserDict
from typing import TYPE_CHECKING, Any, TypedDict

from pickaladder.core.types import FirestoreDocument

if TYPE_CHECKING:
    from pickaladder.user import User


class Group(UserDict):
    """A wrapper class for group data that provides methods for templates."""

    def can_edit(self, user: Any) -> bool:
        """Return True if the user has permission to edit the group."""
        if not user:
            return False
        uid = user.get("uid") if hasattr(user, "get") else getattr(user, "uid", None)
        if not uid:
            return False
        owner_ref = self.get("ownerRef")
        if owner_ref and owner_ref.id == uid:
            return True
        admins = self.get("admins", [])
        return uid in admins

    def is_owner(self, user: Any) -> bool:
        """Return True if the user is the owner of the group."""
        if not user:
            return False
        uid = user.get("uid") if hasattr(user, "get") else getattr(user, "uid", None)
        owner_ref = self.get("ownerRef")
        return bool(owner_ref and owner_ref.id == uid)


class Member(TypedDict, total=False):
    """Represents a group member."""

    userRef: User | Any
    status: str
    role: str


class GroupDict(FirestoreDocument, total=False):
    """A group document in Firestore."""

    name: str
    description: str
    members: list[Member]
    ownerRef: User | Any
    is_public: bool
    profilePictureUrl: str

    # UI and calculated fields
    owner: User | dict[str, Any]
