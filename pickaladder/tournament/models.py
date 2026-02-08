"""Data models for the tournament blueprint."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

from pickaladder.core.types import FirestoreDocument

if TYPE_CHECKING:
    from pickaladder.user.models import User


class Participant(TypedDict, total=False):
    """Represents a tournament participant."""

    userRef: User | Any
    user_id: str
    status: str
    team_name: str
    email: str


class Tournament(FirestoreDocument, total=False):
    """A tournament document in Firestore."""

    name: str
    status: str
    date: Any
    location: str
    matchType: str
    organizer_id: str
    ownerRef: User | Any
    participants: list[Participant]
    participant_ids: list[str]
