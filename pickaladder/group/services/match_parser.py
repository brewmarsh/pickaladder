"""Utility functions for parsing match data and resolving IDs."""

from __future__ import annotations

from typing import Any


def _extract_team_ids(data: dict[str, Any]) -> tuple[set[str], set[str]]:
    """Extract team member IDs, handling Refs, IDs, and legacy formats."""
    t1: set[str] = set()
    # Check 'team1' list
    if "team1" in data:
        team1 = data["team1"]
        if isinstance(team1, list):
            for r in team1:
                if hasattr(r, "id"):
                    t1.add(r.id)
                elif isinstance(r, str):
                    t1.add(r)

    # Check individual fields for Team 1
    team1_fields = [
        "player1Ref",
        "partnerRef",
        "player1Id",
        "partnerId",
        "team1Ref",
    ]
    for field in team1_fields:
        val = data.get(field)
        if val:
            if hasattr(val, "id"):
                t1.add(val.id)
            elif isinstance(val, str):
                t1.add(val)

    t2: set[str] = set()
    # Check 'team2' list
    if "team2" in data:
        team2 = data["team2"]
        if isinstance(team2, list):
            for r in team2:
                if hasattr(r, "id"):
                    t2.add(r.id)
                elif isinstance(r, str):
                    t2.add(r)

    # Check individual fields for Team 2
    team2_fields = [
        "player2Ref",
        "opponent2Ref",
        "player2Id",
        "opponent2Id",
        "team2Ref",
    ]
    for field in team2_fields:
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
    return int(p1_score or 0), int(p2_score or 0)


def _resolve_team_ids(data: dict[str, Any]) -> tuple[str | None, str | None]:
    """Extract Team document IDs if available."""
    t1_id = None
    t1_ref = data.get("team1Ref")
    if t1_ref and hasattr(t1_ref, "id"):
        t1_id = t1_ref.id
    elif isinstance(t1_ref, str):
        t1_id = t1_ref
    else:
        t1_id = data.get("team1Id")

    t2_id = None
    t2_ref = data.get("team2Ref")
    if t2_ref and hasattr(t2_ref, "id"):
        t2_id = t2_ref.id
    elif isinstance(t2_ref, str):
        t2_id = t2_ref
    else:
        t2_id = data.get("team2Id")

    return t1_id, t2_id
