"""Data models for the match blueprint."""

from __future__ import annotations

from collections import UserDict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypedDict

from pickaladder.core.types import FirestoreDocument

if TYPE_CHECKING:
    from pickaladder.user import User


class Match(UserDict):
    """A wrapper class for match data that provides methods for templates."""

    def can_edit(self, user: Any) -> bool:
        """Return True if the user has permission to edit the match."""
        if not user:
            return False
        uid = user.get("uid") if hasattr(user, "get") else getattr(user, "uid", None)
        if not uid:
            return False
        is_admin = getattr(user, "isAdmin", user.get("isAdmin", False))
        if is_admin:
            return True
        return self.get("created_by") == uid and not self.get("tournament_id")

    @property
    def display_date(self) -> str:
        """Return a formatted date string for display."""
        return str(self.get("date") or self.get("match_date") or "N/A")

    @property
    def is_doubles(self) -> bool:
        """Return True if the match is doubles."""
        return self.get("match_type") == "doubles" or self.get("matchType") == "doubles"

    def get_matchup_info(self, user: Any) -> dict[str, Any]:
        """Return matchup information relative to the given user."""
        res = {"user_partner": None, "opponent_name": "Unknown", "is_user_p1": False}
        uid = (
            user.get("uid")
            if user and hasattr(user, "get")
            else getattr(user, "uid", None)
        )
        if not uid:
            return res

        if self.is_doubles:
            p1 = self.get("player1", [])
            p1_ids = [
                p.get("id") if isinstance(p, dict) else getattr(p, "id", None)
                for p in p1
            ]
            in_team1 = uid in p1_ids

            if in_team1:
                if len(p1) > 1:
                    p1_0_id = (
                        p1[0].get("id")
                        if isinstance(p1[0], dict)
                        else getattr(p1[0], "id", None)
                    )
                    res["user_partner"] = p1[1] if p1_0_id == uid else p1[0]
                res["opponent_name"] = self.get("team2_name", "Team 2")
                res["is_user_p1"] = True
            else:
                p2 = self.get("player2", [])
                p2_ids = [
                    p.get("id") if isinstance(p, dict) else getattr(p, "id", None)
                    for p in p2
                ]
                if uid in p2_ids:
                    if len(p2) > 1:
                        p2_0_id = (
                            p2[0].get("id")
                            if isinstance(p2[0], dict)
                            else getattr(p2[0], "id", None)
                        )
                        res["user_partner"] = p2[1] if p2_0_id == uid else p2[0]
                    res["opponent_name"] = self.get("team1_name", "Team 1")
        else:
            p1_data = self.get("player_1_data") or {}
            p2_data = self.get("player_2_data") or {}
            p1_uid = p1_data.get("uid") or getattr(self.get("player1", {}), "id", None)
            p2_uid = p2_data.get("uid") or getattr(self.get("player2", {}), "id", None)

            if uid == p1_uid:
                res["opponent_name"] = p2_data.get("display_name") or "Opponent"
                res["is_user_p1"] = True
            elif uid == p2_uid:
                res["opponent_name"] = p1_data.get("display_name") or "Opponent"
                res["is_user_p1"] = True

        return res

    def get_user_result(self, user: Any) -> str | None:
        """Return the match result for the given user ('win', 'loss', or None)."""
        uid = (
            user.get("uid")
            if user and hasattr(user, "get")
            else getattr(user, "uid", None)
        )
        if not uid:
            return self.get("user_result")

        s1 = self.get("player1_score", 0)
        s2 = self.get("player2_score", 0)
        if s1 == s2:
            return None

        is_p1 = False
        if self.is_doubles:
            p1 = self.get("player1", [])
            p1_ids = [
                p.get("id") if isinstance(p, dict) else getattr(p, "id", None)
                for p in p1
            ]
            is_p1 = uid in p1_ids
        else:
            p1_data = self.get("player_1_data") or {}
            p1_uid = p1_data.get("uid") or getattr(self.get("player1", {}), "id", None)
            is_p1 = uid == p1_uid

        if s1 > s2:
            return "win" if is_p1 else "loss"
        return "loss" if is_p1 else "win"

    def get_score_display(self, user: Any) -> tuple[int, int]:
        """Return (user_score, opponent_score) tuple."""
        uid = (
            user.get("uid")
            if user and hasattr(user, "get")
            else getattr(user, "uid", None)
        )
        s1 = self.get("player1_score", 0)
        s2 = self.get("player2_score", 0)

        if self.is_doubles:
            p1 = self.get("player1", [])
            p1_ids = [
                p.get("id") if isinstance(p, dict) else getattr(p, "id", None)
                for p in p1
            ]
            in_team1 = uid in p1_ids if uid else False
            return (s1, s2) if in_team1 else (s2, s1)
        else:
            p1_data = self.get("player_1_data") or {}
            p1_uid = p1_data.get("uid") or getattr(self.get("player1", {}), "id", None)
            is_p1 = uid == p1_uid
            return (s1, s2) if is_p1 else (s2, s1)


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
    winners: list[str] | None = None
    losers: list[str] | None = None
    participants: list[str] | None = None
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


class MatchDict(FirestoreDocument, Score, total=False):
    """
    A match document in Firestore.
    (Retained as a TypedDict for strict typing in backend services)
    """

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
    winners: list[str]
    losers: list[str]
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
