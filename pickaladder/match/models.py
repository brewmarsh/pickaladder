"""Data models for the match blueprint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypedDict

if TYPE_CHECKING:
    from google.cloud.firestore_v1.document import DocumentSnapshot, DocumentReference
    from pickaladder.user.models import User
    from pickaladder.core.types import FirestoreDocument


@dataclass
class MatchSubmission:
    """Data submitted when recording a match, supporting singles and doubles."""

    match_type: str
    player_1_id: str
    player_2_id: str
    score_p1: int
    score_p2: int
    match_date: Any = None
    group_id: str | None = None
    tournament_id: str | None = None
    partner_id: str | None = None
    opponent_2_id: str | None = None
    created_by: str | None = None


@dataclass
class MatchResult:
    """The result of a recorded match, enriched with metadata for the UI."""

    id: str
    matchType: str
    player1Score: int
    player2Score: int
    matchDate: Any
    createdAt: Any
    createdBy: str
    winner: str
    winnerId: str
    loserId: str
    groupId: str | None = None
    tournamentId: str | None = None
    player1Ref: DocumentReference | None = None
    player2Ref: DocumentReference | None = None
    team1: list[DocumentReference] | None = None
    team2: list[DocumentReference] | None = None
    team1Id: str | None = None
    team2Id: str | None = None
    team1Ref: Any = None
    team2Ref: Any = None
    is_upset: bool = False
    # Post-match rating data (Merged from fix branch)
    match_doc: Any | None = None
    player1_new_rating: float | None = None
    player2_new_rating: float | None = None
    rating_change: float | None = None


class Score(TypedDict, total=False):
    """Represents a match score."""

    player1Score: int
    player2Score: int


class Match(Score, total=False):
    """A match document as it exists in Firestore, including UI-calculated fields."""

    matchType: str
    matchDate: Any
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

    # UI and calculated fields for Dashboard rendering
    player1: User | list[User] | dict[str, Any]
    player2: User | list[User] | dict[str, Any]
    player1_score: int
    player2_score: int
    winner: str
    date: str
    match_date: Any
    is_group_match: bool
    match_type: str
    user_result: str
    team1_name: str
    team2_name: str
    tournament_name: str
    point_differential: int
    close_call: bool
    winner_name: str
    loser_name: str
    winner_score: int
    loser_score: int

    # Denormalized player data snapshots
    player_1_data: dict[str, Any]
    player_2_data: dict[str, Any]