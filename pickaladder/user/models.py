"""Data models for the user blueprint."""

from collections import UserDict

from flask_login import UserMixin


class User(UserDict, UserMixin):
    """A wrapper class for user data that provides additional properties."""

    def get_id(self) -> str:
        """Return the user ID."""
        return str(self.get("uid", ""))

    @property
    def avatar_url(self) -> str:
        """Return a deterministic avatar URL based on the user ID."""
        # Try to get the user ID from various common keys

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
