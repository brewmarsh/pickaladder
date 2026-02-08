"""Data models for the user blueprint."""

from collections import UserDict
from typing import TypedDict

from flask_login import UserMixin

from pickaladder.core.types import FirestoreDocument


class FriendRequest(TypedDict, total=False):
    """A friend request document in Firestore."""

    status: str
    initiator: bool


class User(FirestoreDocument, total=False):
    """A user document in Firestore."""

    email: str
    username: str
    name: str
    is_ghost: bool
    profilePictureUrl: str
    profilePictureThumbnailUrl: str
    dupr_id: str
    dupr_rating: float
    duprRating: float
    isAdmin: bool
    lastMatchRecordedType: str
    dark_mode: bool
    email_verified: bool
    uid: str


class UserSession(UserDict, UserMixin):
    """A wrapper class for user data that provides properties for Flask-Login."""

    def get_id(self) -> str:
        """Return the user ID."""
        return str(self.get("uid", ""))

    @property
    def avatar_url(self) -> str:
        """Return a deterministic avatar URL based on the user ID."""
        # If the user has a profile picture, use it
        thumbnail = self.get("profilePictureThumbnailUrl")
        if thumbnail:
            return str(thumbnail)
        profile_pic = self.get("profilePictureUrl")
        if profile_pic:
            return str(profile_pic)

        # Fallback to DiceBear Avatars (avataaars style)
        seed = self.get("username") or self.get("email") or "User"
        return f"https://api.dicebear.com/9.x/avataaars/svg?seed={seed}"
