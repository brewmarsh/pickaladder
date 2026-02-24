from __future__ import annotations
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client

def get_users_map(db: Client, user_refs: set[Any]) -> dict[str, Any]:
    """Batch fetch users and return a map."""
    users_map: dict[str, Any] = {}
    if not user_refs:
        return users_map
    for doc in db.get_all(list(user_refs)):
        if doc.exists and (d := doc.to_dict()):
            d["id"] = doc.id
            users_map[doc.id] = d
    return users_map

def get_teams_map(db: Client, team_refs: set[Any]) -> dict[str, Any]:
    """Batch fetch teams and return a map."""
    teams_map: dict[str, Any] = {}
    if not team_refs:
        return teams_map
    for doc in db.get_all(list(team_refs)):
        if doc.exists and (d := doc.to_dict()):
            d["id"] = doc.id
            teams_map[doc.id] = d
    return teams_map

def get_tournaments_map(db: Client, tournament_ids: set[str]) -> dict[str, Any]:
    """Batch fetch tournaments and return a map."""
    tournaments_map: dict[str, Any] = {}
    if not tournament_ids:
        return tournaments_map
    t_refs = [db.collection("tournaments").document(tid) for tid in tournament_ids]
    for doc in db.get_all(t_refs):
        if doc.exists and (d := doc.to_dict()):
            d["id"] = doc.id
            tournaments_map[doc.id] = d
    return tournaments_map

def fetch_match_entities(
    db: Client, user_refs: set[Any], team_refs: set[Any], tournament_ids: set[str]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Batch fetch users, teams, and tournaments from Firestore."""
    return (
        get_users_map(db, user_refs),
        get_teams_map(db, team_refs),
        get_tournaments_map(db, tournament_ids),
    )
