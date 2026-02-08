"""Service module for parsing match data."""

from __future__ import annotations

from typing import Any


def _resolve_team_ids(
    data: dict[str, Any], team_key: str, player_prefix: str, partner_prefix: str
) -> set[str]:
    """Resolve player IDs for a single team from various possible fields."""
    team_ids: set[str] = set()

    # 1. Handle list of refs, dicts, or strings in the team_key field
    # (e.g., 'team1', 'team2')
    team_data = data.get(team_key)
    if isinstance(team_data, list):
        for r in team_data:
            if hasattr(r, "id"):
                team_ids.add(r.id)
            elif isinstance(r, dict) and "id" in r:
                team_ids.add(r["id"])
            elif isinstance(r, str):
                team_ids.add(r)

    # 2. Check individual fields for the team
    # e.g., player1Ref, partnerRef, player1Id, partnerId
    # or player2Ref, opponent2Ref, player2Id, opponent2Id
    fields = [
        f"{player_prefix}Ref",
        f"{partner_prefix}Ref",
        f"{player_prefix}Id",
        f"{partner_prefix}Id",
    ]
    for field in fields:
        val = data.get(field)
        if val:
            if hasattr(val, "id"):
                team_ids.add(val.id)
            elif isinstance(val, dict) and "id" in val:
                team_ids.add(val["id"])
            elif isinstance(val, str):
                team_ids.add(val)

    return team_ids


def _extract_team_ids(data: dict[str, Any]) -> tuple[set[str], set[str]]:
    """Extract team member IDs, handling Refs, IDs, and legacy formats."""
    t1 = _resolve_team_ids(data, "team1", "player1", "partner")
    t2 = _resolve_team_ids(data, "team2", "player2", "opponent2")
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
