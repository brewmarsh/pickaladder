"""Data models for the tournament blueprint."""

from __future__ import annotations

from collections import UserDict
from typing import TYPE_CHECKING, Any, TypedDict

from pickaladder.core.types import FirestoreDocument

if TYPE_CHECKING:
    from pickaladder.user import User


class Tournament(UserDict):
    """A wrapper class for tournament data that provides methods for templates."""

    def can_edit(self, user: Any) -> bool:
        """Return True if the user has permission to edit the tournament."""
        if not user:
            return False
        uid = user.get("uid") if hasattr(user, "get") else getattr(user, "uid", None)
        if not uid:
            return False
        owner_id = self.get("organizer_id")
        owner_ref = self.get("ownerRef")
        if not owner_id and owner_ref:
            owner_id = getattr(owner_ref, "id", None)
        is_admin = getattr(user, "isAdmin", user.get("isAdmin", False))
        return uid == owner_id or is_admin

    @property
    def is_doubles(self) -> bool:
        """Return True if the tournament is doubles."""
        return (
            str(self.get("matchType", "")).lower() == "doubles"
            or self.get("mode") == "DOUBLES"
        )

    @property
    def status_badge_class(self) -> str:
        """Return the CSS class for the status badge."""
        return "badge-success" if self.get("status") == "Completed" else "badge-warning"

    @property
    def display_date(self) -> str:
        """Return a formatted date string for display."""
        return str(self.get("date_display") or self.get("date", ""))

    @property
    def location_display(self) -> str:
        """Return a formatted location string."""
        if loc_data := self.get("location_data"):
            return str(loc_data.get("name") or self.get("location", ""))
        return str(self.get("venue_name") or self.get("location", ""))


class Participant(TypedDict, total=False):
    """Represents a tournament participant."""

    userRef: User | Any
    user_id: str
    status: str
    team_name: str
    email: str


class TournamentTeam(TypedDict, total=False):
    """Represents a team within a tournament sub-collection."""

    p1_uid: str
    p2_uid: str
    team_name: str
    status: str  # CONFIRMED/PENDING


class TournamentDict(FirestoreDocument, total=False):
    """A tournament document in Firestore."""

    name: str
    status: str  # DRAFT, PUBLISHED, IN_PROGRESS, COMPLETED
    format: str  # SINGLE_ELIMINATION, ROUND_ROBIN, DOUBLE_ELIMINATION
    date: Any
    location: str
    matchType: str
    mode: str
    organizer_id: str
    ownerRef: User | Any
    participants: list[Participant]
    participant_ids: list[str]

    # UI and calculated fields
    date_display: str
    winner_name: str
