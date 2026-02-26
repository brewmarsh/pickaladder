"""Data models for the user blueprint."""

from __future__ import annotations

from collections import UserDict
from typing import Any, TypedDict

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
    # UI and calculated fields
    wins: int
    losses: int
    games_played: int
    win_percentage: float
    thumbnail_url: str


class UserStats(TypedDict, total=False):
    """Performance statistics for a user."""

    wins: int
    losses: int
    total_games: int
    win_rate: float
    current_streak: int
    streak_type: str
    processed_matches: list[dict[str, Any]]


class UserRanking(TypedDict, total=False):
    """A user's ranking within a group."""

    group_id: str
    group_name: str
    rank: int | str
    points: float
    form: list[str]
    player_above: str
    points_to_overtake: float


class UserSession(UserDict, UserMixin):
    """A wrapper class for user data that provides properties for Flask-Login."""

    def get_id(self) -> str:
        """Return the user ID."""
        return str(self.get("uid", ""))

    @property
    def is_admin(self) -> bool:
        """Return True if the user is an administrator."""
        return self.get("isAdmin", False)

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

        # Fallback to "default"
        return "default"
