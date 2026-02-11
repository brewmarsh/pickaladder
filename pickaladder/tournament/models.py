"""Data models for the tournament blueprint."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

from pickaladder.core.types import FirestoreDocument

if TYPE_CHECKING:
    from pickaladder.user import User


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


class Tournament(FirestoreDocument, total=False):
    """A tournament document in Firestore."""

    name: str
    status: str
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
