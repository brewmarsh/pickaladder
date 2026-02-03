"""Data models for the user blueprint."""

from collections import UserDict


class User(UserDict):
    """A wrapper class for user data that provides additional properties."""

    @property
    def avatar_url(self) -> str:
        """Return a deterministic avatar URL based on the user ID."""
        # Try to get the user ID from various common keys
        user_id = self.get("uid") or self.get("id") or self.get("userId")

        # If the user has a profile picture, use it
        thumbnail = self.get("profilePictureThumbnailUrl")
        if thumbnail:
            return str(thumbnail)
        profile_pic = self.get("profilePictureUrl")
        if profile_pic:
            return str(profile_pic)

        # Fallback to DiceBear API
        # Using brand colors: Green (2e7d32), Amber (ffc107), Blue (1976d2)
        seed = user_id or self.get("username") or "default"
        return f"https://api.dicebear.com/7.x/avataaars/svg?seed={seed}&backgroundColor=2e7d32,ffc107,1976d2"
