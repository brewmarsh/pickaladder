from __future__ import annotations

from typing import Any


def _get_ids_from_refs(refs: list[Any]) -> set[str]:
    """Helper to extract string IDs from a list of references or strings."""
    return {str(r.id if hasattr(r, "id") else r) for r in refs if r}


def _extract_id_from_match_slot(
    slot_ref: Any, slot_data: dict[str, Any], slot_id: Any
) -> str:
    """Extract ID from reference, dictionary data, or direct ID string."""
    return str(
        (slot_ref.id if slot_ref and hasattr(slot_ref, "id") else "")
        or slot_data.get("uid")
        or slot_id
        or ""
    )


def _get_singles_ids(data: dict[str, Any]) -> tuple[set[str], set[str]]:
    """Extract member IDs from a singles match."""
    id1 = _extract_id_from_match_slot(
        data.get("player1Ref"), data.get("player_1_data", {}), data.get("player1Id")
    )
    id2 = _extract_id_from_match_slot(
        data.get("player2Ref"), data.get("player_2_data", {}), data.get("player2Id")
    )
    return {id1}, {id2}


def _get_team_ids_from_match(data: dict[str, Any]) -> tuple[set[str], set[str]]:
    """Extract team 1 and team 2 member IDs from a match."""
    if data.get("matchType") == "doubles":
        return _get_ids_from_refs(data.get("team1", [])), _get_ids_from_refs(
            data.get("team2", [])
        )

    return _get_singles_ids(data)


def _evaluate_win_loss(score_a: int, score_b: int) -> tuple[bool, bool]:
    """Helper to evaluate win/loss status based on scores."""
    return (score_a > score_b), (score_a < score_b)


def _get_user_match_won_lost(
    match_data: dict[str, Any], user_id: str
) -> tuple[bool, bool]:
    """Determine if the user won or lost the match, including handling of draws."""
    p1_score = int(match_data.get("player1Score", 0))
    p2_score = int(match_data.get("player2Score", 0))

    if p1_score == p2_score:
        return False, False

    t1_ids, t2_ids = _get_team_ids_from_match(match_data)
    if user_id in t1_ids:
        return _evaluate_win_loss(p1_score, p2_score)
    if user_id in t2_ids:
        return _evaluate_win_loss(p2_score, p1_score)

    return False, False


def _get_user_match_result(
    match_dict: dict[str, Any], user_id: str, winner_slot: str
) -> str:
    """Determine if the user won or lost the match."""
    won, lost = _get_user_match_won_lost(match_dict, user_id)
    if won:
        return "win"
    if lost:
        return "loss"
    return "draw"


def _get_match_winner_slot(match_dict: dict[str, Any]) -> str:
    """Determine the winner slot ('team1' or 'team2')."""
    p1_score = match_dict.get("player1Score", 0)
    p2_score = match_dict.get("player2Score", 0)
    return "team1" if p1_score > p2_score else "team2"
