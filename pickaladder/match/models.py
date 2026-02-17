"""Data models for the match blueprint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypedDict

from pickaladder.core.types import FirestoreDocument

if TYPE_CHECKING:
    from google.cloud.firestore_v1.document import DocumentReference
    from pickaladder.user import User


class Score(TypedDict, total=False):
    """Represents a match score."""
    player1Score: int
    player2Score: int


class Match(FirestoreDocument, Score, total=False):
    """A match document in Firestore."""
    id: str
    player1: str
    player2: str
    matchType: str
    matchDate: Any
    createdAt: Any
    createdBy: str
    winner: str
    winnerId: str
    loserId: str
    groupId: str
    tournamentId: str
    player1Ref: DocumentReference | User | Any
    player2Ref: DocumentReference | User | Any
    team1: list[DocumentReference | User | Any]
    team2: list[DocumentReference | User | Any]
    team1Id: str
    team2Id: str
    team1Ref: DocumentReference | Any
    team2Ref: DocumentReference | Any
    is_upset: bool
    point_differential: int
    close_call: bool
    date: str
    winner_name: str
    loser_name: str
    winner_score: int
    loser_score: int
    player_1_data: dict[str, Any]
    player_2_data: dict[str, Any]


@dataclass
class MatchSubmission:
    """A match submission from the frontend."""
    player1: str
    player2: str
    player1_score: int
    player2_score: int
    group_id: str | None = None
    tournament_id: str | None = None
    match_type: str | None = None
    match_date: Any | None = None
    partner: str | None = None
    opponent2: str | None = None

    def __getitem__(self, key: str) -> Any:
        """Allow dict-like access for backward compatibility."""
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        """Allow dict-like get for backward compatibility."""
        return getattr(self, key, default)


@dataclass
class MatchResult:
    """The result of recording a match."""
    id: str
    matchType: str | None = None
    player1Score: int | None = None
    player2Score: int | None = None
    matchDate: Any | None = None
    createdAt: Any | None = None
    createdBy: str | None = None
    winner: str | None = None
    winnerId: str | None = None
    loserId: str | None = None
    groupId: str | None = None
    tournamentId: str | None = None
    player1Ref: DocumentReference | None = None
    player2Ref: DocumentReference | None = None
    team1: list[DocumentReference] | None = None
    team2: list[DocumentReference] | None = None
    team1Id: str | None = None
    team2Id: str | None = None
    team1Ref: DocumentReference | None = None
    team2Ref: DocumentReference | None = None
    is_upset: bool = False
    match_doc: Any | None = None
    player1_new_rating: float | None = None
    player2_new_rating: float | None = None
    rating_change: float | None = None