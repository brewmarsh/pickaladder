"""Data models for the group blueprint."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

from pickaladder.core.types import FirestoreDocument

if TYPE_CHECKING:
    from pickaladder.user.models import User


class Member(TypedDict, total=False):
    """Represents a group member."""

    userRef: User | Any
    status: str
    role: str


class Group(FirestoreDocument, total=False):
    """A group document in Firestore."""

    name: str
    description: str
    members: list[Member]
    ownerRef: User | Any
    is_public: bool
    profilePictureUrl: str

    # UI and calculated fields
    owner: User | dict[str, Any]
