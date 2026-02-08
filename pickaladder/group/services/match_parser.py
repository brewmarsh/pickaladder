"""Low-level data helpers for match parsing."""

from typing import Any


def _extract_team_ids(data: dict[str, Any]) -> tuple[set[str], set[str]]:
    """Extract team member IDs, handling Refs, IDs, and legacy formats."""
    t1: set[str] = set()
    if "team1" in data:
        # Handle list of refs or strings in 'team1'
        team1 = data["team1"]
        if isinstance(team1, list):
            for r in team1:
                if hasattr(r, "id"):
                    t1.add(r.id)
                elif isinstance(r, str):
                    t1.add(r)

    # Check individual fields for Team 1
    for field in ["player1Ref", "partnerRef", "player1Id", "partnerId"]:
        val = data.get(field)
        if val:
            if hasattr(val, "id"):
                t1.add(val.id)
            elif isinstance(val, str):
                t1.add(val)

    t2: set[str] = set()
    if "team2" in data:
        # Handle list of refs or strings in 'team2'
        team2 = data["team2"]
        if isinstance(team2, list):
            for r in team2:
                if hasattr(r, "id"):
                    t2.add(r.id)
                elif isinstance(r, str):
                    t2.add(r)

    # Check individual fields for Team 2
    for field in ["player2Ref", "opponent2Ref", "player2Id", "opponent2Id"]:
        val = data.get(field)
        if val:
            if hasattr(val, "id"):
                t2.add(val.id)
            elif isinstance(val, str):
                t2.add(val)

    return t1, t2


def _get_match_scores(data: dict[str, Any]) -> tuple[int, int]:
    """Get team 1 and team 2 scores, handling both singles and doubles fields."""
    p1_score = data.get("player1Score")
    if p1_score is None:
        p1_score = data.get("team1Score", 0)
    p2_score = data.get("player2Score")
    if p2_score is None:
        p2_score = data.get("team2Score", 0)
    return p1_score, p2_score
