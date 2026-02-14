"""Data models for the match blueprint."""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypedDict

from pickaladder.core.types import FirestoreDocument

if TYPE_CHECKING:
    from pickaladder.user import User


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


@dataclass
class MatchSubmission:
    """Dataclass for match recording submission."""

    player_1_id: str
    player_2_id: str
    score_p1: int
    score_p2: int
    match_type: str = "singles"
    partner_id: str | None = None
    opponent_2_id: str | None = None
    group_id: str | None = None
    tournament_id: str | None = None
    match_date: datetime.date | datetime.datetime | None = None
    created_by: str | None = None

    def validate(self) -> None:
        """Validate the match submission for obvious errors."""
        if self.score_p1 < 0 or self.score_p2 < 0:
            raise ValueError("Scores cannot be negative.")
        if self.score_p1 == self.score_p2:
            raise ValueError("Scores cannot be the same.")

        min_winning_score = 11
        min_win_margin = 2
        if max(self.score_p1, self.score_p2) < min_winning_score:
            raise ValueError(
                f"One team/player must have at least {min_winning_score} points to win."
            )
        if abs(self.score_p1 - self.score_p2) < min_win_margin:
            raise ValueError(
                f"The winner must win by at least {min_win_margin} points."
            )

        if self.match_type == "doubles":
            if not self.partner_id or not self.opponent_2_id:
                raise ValueError("Partner and Opponent 2 are required for doubles.")
            players = [
                self.player_1_id,
                self.partner_id,
                self.player_2_id,
                self.opponent_2_id,
            ]
            active_players = [p for p in players if p]
            if len(active_players) != len(set(active_players)):
                raise ValueError("All players in a doubles match must be unique.")
        elif self.player_1_id == self.player_2_id:
            raise ValueError("You can't play against yourself.")


@dataclass
class MatchResult:
    """Dataclass representing a recorded match result, matching Firestore structure."""

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
    player1Ref: Any | None = None
    player2Ref: Any | None = None
    team1: list[Any] | None = None
    team2: list[Any] | None = None
    team1Id: str | None = None
    team2Id: str | None = None
    team1Ref: Any | None = None
    team2Ref: Any | None = None
    is_upset: bool = False
