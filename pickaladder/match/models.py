"""Data models for the match blueprint."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional, TypedDict

from pickaladder.core.types import FirestoreDocument

if TYPE_CHECKING:
    from pickaladder.user import User


@dataclass
class MatchSubmission:
    """Represents a match submission."""

    match_type: str
    player_1_id: str
    player_2_id: str
    score_p1: int
    score_p2: int
    match_date: Any
    partner_id: str | None = None
    opponent_2_id: str | None = None
    group_id: str | None = None
    tournament_id: str | None = None
    created_by: str | None = None

    def __getitem__(self, key: str) -> Any:
        """Allow dict-like access for backward compatibility or convenience."""
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        """Allow dict-like get for backward compatibility."""
        return getattr(self, key, default)


@dataclass
class MatchResult:
    """Represents the result of recording a match."""

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
    is_upset: bool = False
    groupId: str | None = None
    tournamentId: str | None = None
    player1Ref: Any = None
    player2Ref: Any = None
    team1: list[Any] | None = None
    team2: list[Any] | None = None
    team1Id: str | None = None
    team2Id: str | None = None
    team1Ref: Any = None
    team2Ref: Any = None


class Score(TypedDict, total=False):
    """Represents a match score."""

    player1Score: int
    player2Score: int


@dataclass
class MatchSubmission:
    """Represents a match submission."""

    player_1_id: str
    player_2_id: str
    score_p1: int
    score_p2: int
    match_type: str
    match_date: Any = None
    partner_id: Optional[str] = None
    opponent_2_id: Optional[str] = None
    group_id: Optional[str] = None
    tournament_id: Optional[str] = None
    created_by: Optional[str] = None

    def __getitem__(self, key: str) -> Any:
        """Allow dict-like access for compatibility."""
        return getattr(self, key)


@dataclass
class MatchResult:
    """Result of recording a match."""

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
    groupId: Optional[str] = None
    tournamentId: Optional[str] = None
    player1Ref: Any = None
    player2Ref: Any = None
    team1: Optional[list[Any]] = None
    team2: Optional[list[Any]] = None
    team1Id: Optional[str] = None
    team2Id: Optional[str] = None
    team1Ref: Any = None
    team2Ref: Any = None
    is_upset: bool = False


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

    # UI and calculated fields
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

    # Denormalized player data
    player_1_data: dict[str, Any]
    player_2_data: dict[str, Any]


@dataclass
class MatchSubmission:
    """Represents a match submission."""

    match_type: str
    player_1_id: str
    player_2_id: str
    score_p1: int
    score_p2: int
    match_date: Any = None
    partner_id: str | None = None
    opponent_2_id: str | None = None
    group_id: str | None = None
    tournament_id: str | None = None
    created_by: str | None = None


@dataclass
class MatchResult:
    """Represents the result of recording a match."""

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
    is_upset: bool = False
    groupId: str | None = None
    tournamentId: str | None = None
    player1Ref: Any = None
    player2Ref: Any = None
    team1: list[Any] | None = None
    team2: list[Any] | None = None
    team1Id: str | None = None
    team2Id: str | None = None
    team1Ref: Any = None
    team2Ref: Any = None
