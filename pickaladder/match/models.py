"""Data models for the match blueprint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypedDict

if TYPE_CHECKING:
    from google.cloud.firestore_v1.document import DocumentReference


class Match(TypedDict, total=False):
    """A match document in Firestore."""

    id: str
    player1: str
    player2: str
    player1Score: int
    player2Score: int
    matchDate: Any
    createdAt: Any
    matchType: str
    winner: str
    winnerId: str
    loserId: str
    groupId: str
    tournamentId: str
    player1Ref: DocumentReference
    player2Ref: DocumentReference
    team1: list[DocumentReference]
    team2: list[DocumentReference]
    team1Id: str
    team2Id: str
    team1Ref: DocumentReference
    team2Ref: DocumentReference
    is_upset: bool
    point_differential: int
    close_call: bool
    date: str
    winner_name: str
    loser_name: str
    winner_score: int
    loser_score: int
    createdBy: str
    player_1_data: dict[str, Any]
    player_2_data: dict[str, Any]


class Score(TypedDict):
    """A score representation."""

    player1: int
    player2: int


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
