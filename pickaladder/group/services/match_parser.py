from __future__ import annotations

"""Service module for parsing match data."""


from typing import Any


def _extract_id(val: Any) -> str | None:
    """Extract an ID from a Firestore reference, dictionary, or string."""
    if hasattr(val, "id"):
        return val.id
    if isinstance(val, dict) and "id" in val:
        return val["id"]
    if isinstance(val, str):
        return val
    return None


def _resolve_team_ids(
    data: dict[str, Any], team_key: str, player_prefix: str, partner_prefix: str
) -> set[str]:
    """Resolve player IDs for a single team from various possible fields."""
    team_ids: set[str] = set()

    # 1. Handle list of refs, dicts, or strings in the team_key field
    # (e.g., 'team1', 'team2')
    team_ids.update(_resolve_from_team_key(data, team_key))

    # 2. Check individual fields for the team
    team_ids.update(
        _resolve_from_individual_fields(data, team_key, player_prefix, partner_prefix)
    )

    return team_ids


def _resolve_from_team_key(data: dict[str, Any], team_key: str) -> set[str]:
    """Resolve IDs from the team_key field if it's a list."""
    team_ids = set()
    team_data = data.get(team_key)
    if isinstance(team_data, list):
        for r in team_data:
            if val_id := _extract_id(r):
                team_ids.add(val_id)
    return team_ids


def _resolve_from_individual_fields(
    data: dict[str, Any], team_key: str, player_prefix: str, partner_prefix: str
) -> set[str]:
    """Resolve IDs from individual player and team fields."""
    team_ids = set()
    fields = [
        f"{player_prefix}Ref",
        f"{partner_prefix}Ref",
        f"{player_prefix}Id",
        f"{partner_prefix}Id",
        f"{team_key}Ref",
    ]
    for field in fields:
        if val_id := _extract_id(data.get(field)):
            team_ids.add(val_id)
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
    return int(p1_score or 0), int(p2_score or 0)


def _resolve_team_document_ids(data: dict[str, Any]) -> tuple[str | None, str | None]:
    """Extract Team document IDs if available."""
    t1_id = _extract_id(data.get("team1Ref")) or data.get("team1Id")
    t2_id = _extract_id(data.get("team2Ref")) or data.get("team2Id")
    return t1_id, t2_id
