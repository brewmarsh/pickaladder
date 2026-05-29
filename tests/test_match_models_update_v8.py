"""Tests for match model updates in Phase 8 Wave 2."""

import datetime

from pickaladder.match.models import MatchDict, MatchResult, MatchSubmission


def test_match_submission_with_named_teams():
    """Verify MatchSubmission supports namedTeamId fields."""
    submission = MatchSubmission(
        match_type="doubles",
        player_1_id="p1",
        player_2_id="p2",
        score_p1=11,
        score_p2=5,
        match_date=datetime.datetime.now(),
        partner_id="p1_partner",
        opponent_2_id="p2_partner",
        namedTeam1Id="team_alpha",
        namedTeam2Id="team_beta",
    )

    assert submission.namedTeam1Id == "team_alpha"
    assert submission.namedTeam2Id == "team_beta"
    assert submission["namedTeam1Id"] == "team_alpha"
    assert submission.get("namedTeam2Id") == "team_beta"


def test_match_result_with_named_teams():
    """Verify MatchResult supports namedTeamId fields."""
    result = MatchResult(
        id="match_123",
        matchType="doubles",
        player1Score=11,
        player2Score=5,
        matchDate=datetime.datetime.now(),
        createdAt=datetime.datetime.now(),
        createdBy="p1",
        winner="team1",
        winnerId="team1_id",
        loserId="team2_id",
        namedTeam1Id="team_alpha",
        namedTeam2Id="team_beta",
    )

    assert result.namedTeam1Id == "team_alpha"
    assert result.namedTeam2Id == "team_beta"


def test_match_dict_typing():
    """Verify MatchDict TypedDict includes namedTeamId fields."""
    # This is more of a static typing check, but we can verify it at runtime
    match_data: MatchDict = {
        "matchType": "doubles",
        "matchDate": datetime.datetime.now(),
        "team1Id": "pairing_1",
        "team2Id": "pairing_2",
        "namedTeam1Id": "team_alpha",
        "namedTeam2Id": "team_beta",
        "status": "completed",
        "is_verified": True,
        "winnerId": "pairing_1",
        "winners": ["p1", "p1_p"],
        "losers": ["p2", "p2_p"],
        "participants": ["p1", "p1_p", "p2", "p2_p"],
    }

    assert match_data["namedTeam1Id"] == "team_alpha"
    assert match_data["namedTeam2Id"] == "team_beta"
