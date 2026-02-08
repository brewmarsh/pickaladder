"""Data models for the match blueprint."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

from pickaladder.core.types import FirestoreDocument

if TYPE_CHECKING:
    from pickaladder.user.models import User


class Score(TypedDict, total=False):
    """Represents a match score."""

    player1Score: int
    player2Score: int


class Match(FirestoreDocument, Score, total=False):
    """A match document in Firestore."""

    matchType: str
    matchDate: Any
    # player1Score and player2Score are inherited from Score
    player1Ref: User | Any
    player2Ref: User | Any
    team1: list[User | Any]
    team2: list[User | Any]
    team1Id: str
    team2Id: str
    team1Ref: Any
    team2Ref: Any
    groupId: str
    tournamentId: str
    status: str
    winnerId: str
    participants: list[str]
