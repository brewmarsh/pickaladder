from __future__ import annotations

from typing import TYPE_CHECKING, Any

from flask import current_app

if TYPE_CHECKING:
    from firebase_admin import firestore as _firestore
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
        current_app.logger.info("Ghost user merge completed successfully.")
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
        matches = db.collection("matches").where(field, "==", ghost_ref).stream()
        for match in matches:
            if match.id not in match_updates:
                match_updates[match.id] = {"ref": match.reference, "data": {}}
            match_updates[match.id]["data"][field] = real_user_ref

    for update in match_updates.values():
        batch.update(update["ref"], update["data"])


def _migrate_doubles_matches(
    db: Client, batch: _firestore.WriteBatch, ghost_ref: Any, real_user_ref: Any
) -> None:
    """Update doubles matches where the user is in a team array."""
    from pickaladder.teams.services import TeamService  # noqa: PLC0415

    match_updates: dict[str, dict[str, Any]] = {}
    for field in ["team1", "team2"]:
        matches = (
            db.collection("matches").where(field, "array_contains", ghost_ref).stream()
        )
        for match in matches:
            if match.id not in match_updates:
                m_data = match.to_dict()
                if not m_data:
                    continue
                match_updates[match.id] = {
                    "ref": match.reference,
                    "full_data": m_data,
                    "updates": {},
                }

            m_data = match_updates[match.id]["full_data"]
            if field in m_data:
                current_team = m_data[field]
                new_team = [
                    real_user_ref if r == ghost_ref else r for r in current_team
                ]
                match_updates[match.id]["updates"][field] = new_team

                # Update team ID resolution logic
                partner_ref = next((r for r in current_team if r != ghost_ref), None)
                if partner_ref:
                    new_team_id = TeamService.get_or_create_team(
                        db, real_user_ref.id, partner_ref.id
                    )
                    id_field = "team1Id" if field == "team1" else "team2Id"
                    ref_field = "team1Ref" if field == "team1" else "team2Ref"
                    match_updates[match.id]["updates"][id_field] = new_team_id
                    match_updates[match.id]["updates"][ref_field] = db.collection(
                        "teams"
                    ).document(new_team_id)

    for update in match_updates.values():
        if update["updates"]:
            batch.update(update["ref"], update["updates"])


def _migrate_groups(
    db: Client, batch: _firestore.WriteBatch, ghost_ref: Any, real_user_ref: Any
) -> None:
    """Update group memberships."""

    groups = (
        db.collection("groups").where("members", "array_contains", ghost_ref).stream()
    )
    for group in groups:
        g_data = group.to_dict()
        if g_data and "members" in g_data:
            current_members = g_data["members"]
            new_members = [
                real_user_ref if m == ghost_ref else m for m in current_members
            ]
            batch.update(group.reference, {"members": new_members})


def _migrate_tournaments(
    db: Client, batch: _firestore.WriteBatch, ghost_ref: Any, real_user_ref: Any
) -> None:
    """Update tournament participant lists and IDs."""

    tournaments = (
        db.collection("tournaments")
        .where("participant_ids", "array_contains", ghost_ref.id)
        .stream()
    )

    for tournament in tournaments:
        data = tournament.to_dict()
        if not data:
            continue

        participants = data.get("participants", [])
        updated = False

        for p in participants:
            if not p:
                continue

            # Check IDs in both formats (ref object or string ID)
            p_ref = p.get("userRef")
            p_uid = p_ref.id if p_ref else p.get("user_id")

            if p_uid == ghost_ref.id:
                if "userRef" in p:
                    p["userRef"] = real_user_ref

                # Ensure at least one ID field is present and correct
                if "user_id" in p or "userRef" in p:
                    p["user_id"] = real_user_ref.id

                updated = True

        if updated:
            p_ids = data.get("participant_ids", [])
            # Rebuild the simple ID list
            new_p_ids = [
                real_user_ref.id if pid == ghost_ref.id else pid for pid in p_ids
            ]
            batch.update(
                tournament.reference,
                {"participants": participants, "participant_ids": new_p_ids},
            )
