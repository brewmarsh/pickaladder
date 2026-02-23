from __future__ import annotations

from typing import TYPE_CHECKING, Any

from flask import current_app

if TYPE_CHECKING:
    from firebase_admin import firestore as _firestore
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client


def merge_ghost_user(db: Client, real_user_ref: Any, email: str) -> bool:
    """Check for 'ghost' user with the given email and merge their data."""
    try:
        query = (
            db.collection("users")
            .where("email", "==", email.lower())
            .where("is_ghost", "==", True)
            .limit(1)
        )
        ghost_docs = list(query.stream())
        if not ghost_docs:
            return False

        ghost_doc = ghost_docs[0]
        current_app.logger.info(
            f"Merging ghost user {ghost_doc.id} to {real_user_ref.id}"
        )
        merge_users(db, ghost_doc.id, real_user_ref.id)
        return True
    except Exception as e:
        current_app.logger.error(f"Error merging ghost user: {e}")
        return False


def merge_users(db: Client, source_id: str, target_id: str) -> None:
    """Perform a deep merge of two user accounts. Source is deleted."""
    from pickaladder.teams.services import TeamService  # noqa: PLC0415

    source_ref = db.collection("users").document(source_id)
    target_ref = db.collection("users").document(target_id)
    batch = db.batch()
    _migrate_user_references(db, batch, source_ref, target_ref)
    TeamService.migrate_user_teams(db, batch, source_id, target_id)
    batch.delete(source_ref)
    batch.commit()


def _migrate_user_references(
    db: Client, batch: _firestore.WriteBatch, ghost_ref: Any, real_user_ref: Any
) -> None:
    """Orchestrate the migration of all user references."""
    _migrate_singles_matches(db, batch, ghost_ref, real_user_ref)
    _migrate_doubles_matches(db, batch, ghost_ref, real_user_ref)
    _migrate_groups(db, batch, ghost_ref, real_user_ref)
    _migrate_tournaments(db, batch, ghost_ref, real_user_ref)


def _migrate_singles_matches(
    db: Client, batch: _firestore.WriteBatch, ghost_ref: Any, real_user_ref: Any
) -> None:
    """Update singles matches where the user is player 1 or 2."""
    match_updates: dict[str, dict[str, Any]] = {}
    for field in ["player1Ref", "player2Ref"]:
        for match in db.collection("matches").where(field, "==", ghost_ref).stream():
            if match.id not in match_updates:
                match_updates[match.id] = {"ref": match.reference, "data": {}}
            match_updates[match.id]["data"][field] = real_user_ref

    for update in match_updates.values():
        batch.update(update["ref"], update["data"])


def _update_doubles_match_team(
    db: Client, match: Any, field: str, refs: tuple[Any, Any], updates: dict[str, Any]
) -> None:
    """Update team data for a doubles match if it contains the ghost user."""
    from pickaladder.teams.services import TeamService  # noqa: PLC0415

    ghost_ref, real_user_ref = refs
    m_data = match.to_dict()
    if not m_data or field not in m_data:
        return

    current_team = m_data[field]
    new_team = [real_user_ref if r == ghost_ref else r for r in current_team]
    updates[field] = new_team

    partner_ref = next((r for r in current_team if r != ghost_ref), None)
    if partner_ref:
        new_team_id = TeamService.get_or_create_team(
            db, real_user_ref.id, partner_ref.id
        )
        id_f, ref_f = (
            ("team1Id", "team1Ref") if field == "team1" else ("team2Id", "team2Ref")
        )
        updates[id_f] = new_team_id
        updates[ref_f] = db.collection("teams").document(new_team_id)


def _fetch_doubles_matches_to_migrate(
    db: Client, field: str, ghost_ref: Any
) -> list[DocumentSnapshot]:
    """Fetch doubles matches for a specific team field containing the ghost user."""
    return list(
        db.collection("matches").where(field, "array_contains", ghost_ref).stream()
    )


def _apply_doubles_migration_batch(
    db: Client,
    batch: _firestore.WriteBatch,
    docs: list[DocumentSnapshot],
    field: str,
    ghost_ref: Any,
    real_user_ref: Any,
) -> None:
    """Prepare and apply batch updates for doubles matches."""
    match_updates: dict[str, dict[str, Any]] = {}
    refs = (ghost_ref, real_user_ref)
    for match in docs:
        if match.id not in match_updates:
            match_updates[match.id] = {"ref": match.reference, "updates": {}}
        _update_doubles_match_team(
            db, match, field, refs, match_updates[match.id]["updates"]
        )

    for update in match_updates.values():
        if update["updates"]:
            batch.update(update["ref"], update["updates"])


def _migrate_doubles_matches(
    db: Client, batch: _firestore.WriteBatch, ghost_ref: Any, real_user_ref: Any
) -> None:
    """Update doubles matches where the user is in a team array."""
    for field in ["team1", "team2"]:
        matches = _fetch_doubles_matches_to_migrate(db, field, ghost_ref)
        _apply_doubles_migration_batch(
            db, batch, matches, field, ghost_ref, real_user_ref
        )


def _migrate_groups(
    db: Client, batch: _firestore.WriteBatch, ghost_ref: Any, real_user_ref: Any
) -> None:
    """Update group memberships."""
    for group in (
        db.collection("groups").where("members", "array_contains", ghost_ref).stream()
    ):
        if g_data := group.to_dict():
            new_members = [
                real_user_ref if m == ghost_ref else m
                for m in g_data.get("members", [])
            ]
            batch.update(group.reference, {"members": new_members})


def _update_tournament_participant(
    p: dict[str, Any], ghost_ref_id: str, real_user_ref: Any
) -> bool:
    """Update a single tournament participant entry."""
    if not p:
        return False
    p_ref = p.get("userRef")
    p_uid = p_ref.id if p_ref else p.get("user_id")

    if p_uid == ghost_ref_id:
        if "userRef" in p:
            p["userRef"] = real_user_ref
        if "user_id" in p or "userRef" in p:
            p["user_id"] = real_user_ref.id
        return True
    return False


def _rebuild_participant_ids(
    p_ids: list[str], ghost_ref_id: str, real_user_ref_id: str
) -> list[str]:
    """Rebuild the simple participant ID list."""
    return [real_user_ref_id if pid == ghost_ref_id else pid for pid in p_ids]


def _fetch_tournaments_to_migrate(
    db: Client, ghost_id: str
) -> list[DocumentSnapshot]:
    """Fetch tournaments where the ghost user is a participant."""
    query = db.collection("tournaments").where(
        "participant_ids", "array_contains", ghost_id
    )
    return list(query.stream())


def _migrate_single_tournament(
    batch: _firestore.WriteBatch,
    tournament_doc: DocumentSnapshot,
    ghost_ref: Any,
    real_user_ref: Any,
) -> None:
    """Migrate a single tournament record from ghost user to real user."""
    data = tournament_doc.to_dict()
    if not data:
        return

    participants = data.get("participants", [])
    updated = any(
        _update_tournament_participant(p, ghost_ref.id, real_user_ref)
        for p in participants
    )
    if updated:
        new_p_ids = _rebuild_participant_ids(
            data.get("participant_ids", []), ghost_ref.id, real_user_ref.id
        )
        batch.update(
            tournament_doc.reference,
            {"participants": participants, "participant_ids": new_p_ids},
        )


def _migrate_tournaments(
    db: Client, batch: _firestore.WriteBatch, ghost_ref: Any, real_user_ref: Any
) -> None:
    """Update tournament participant lists and IDs."""
    tournaments = _fetch_tournaments_to_migrate(db, ghost_ref.id)
    for tournament in tournaments:
        _migrate_single_tournament(batch, tournament, ghost_ref, real_user_ref)
