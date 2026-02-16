"""Service layer for team-related business logic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from firebase_admin import firestore

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client


class TeamService:
    """Handles business logic for teams (doubles partnerships)."""

    @staticmethod
    def get_or_create_team(db: Client, p1_uid: str, p2_uid: str) -> str:
        """Find an existing team or create a new one for two players."""
        # Sort UIDs to ensure deterministic team identity
        member_ids = sorted([p1_uid, p2_uid])

        teams_ref = db.collection("teams")
        query = teams_ref.where("member_ids", "==", member_ids).limit(1)
        docs = list(query.stream())

        if docs:
            return str(docs[0].id)

        # Create new team
        team_data = {
            "member_ids": member_ids,
            "member_refs": [
                db.collection("users").document(p1_uid),
                db.collection("users").document(p2_uid),
            ],
            "createdAt": firestore.SERVER_TIMESTAMP,
            "name": f"Team {member_ids[0][:4]} & {member_ids[1][:4]}",
        }
        _, ref = teams_ref.add(team_data)
        return str(ref.id)

    @staticmethod
    def merge_teams_for_ghost(
        db: Client, ghost_id: str, real_id: str, batch: Any = None
    ) -> None:
        """Merge all teams containing a ghost user into real user teams."""
        teams_ref = db.collection("teams")
        teams_query = teams_ref.where("member_ids", "array_contains", ghost_id).stream()

        for team_doc in teams_query:
            team_data = team_doc.to_dict()
            if not team_data:
                continue

            old_member_ids = team_data.get("member_ids", [])
            new_member_ids = sorted(
                [real_id if uid == ghost_id else uid for uid in old_member_ids]
            )

            # Check if a team with the new member combination already exists
            existing_team_query = teams_ref.where(
                "member_ids", "==", new_member_ids
            ).limit(1)
            existing_docs = list(existing_team_query.stream())

            if existing_docs:
                # Merge matches from old team to existing team
                target_team_id = existing_docs[0].id
                TeamService._migrate_team_matches(
                    db, team_doc.id, target_team_id, batch
                )
                if batch:
                    batch.delete(team_doc.reference)
                else:
                    team_doc.reference.delete()
            else:
                # Update the existing team document
                update_data = {
                    "member_ids": new_member_ids,
                    "member_refs": [
                        db.collection("users").document(uid) for uid in new_member_ids
                    ],
                    "updatedAt": firestore.SERVER_TIMESTAMP,
                }
                if batch:
                    batch.update(team_doc.reference, update_data)
                else:
                    team_doc.reference.update(update_data)

    @staticmethod
    def _migrate_team_matches(
        db: Client, source_id: str, target_id: str, batch: Any = None
    ) -> None:
        """Update all matches referencing source_id to target_id."""
        matches_ref = db.collection("matches")

        # Update matches where team was team1
        q1 = matches_ref.where("team1Id", "==", source_id).stream()
        for match in q1:
            if batch:
                batch.update(
                    match.reference,
                    {
                        "team1Id": target_id,
                        "team1Ref": db.collection("teams").document(target_id),
                    },
                )
            else:
                match.reference.update(
                    {
                        "team1Id": target_id,
                        "team1Ref": db.collection("teams").document(target_id),
                    }
                )

        # Update matches where team was team2
        q2 = matches_ref.where("team2Id", "==", source_id).stream()
        for match in q2:
            if batch:
                batch.update(
                    match.reference,
                    {
                        "team2Id": target_id,
                        "team2Ref": db.collection("teams").document(target_id),
                    },
                )
            else:
                match.reference.update(
                    {
                        "team2Id": target_id,
                        "team2Ref": db.collection("teams").document(target_id),
                    }
                )

    @staticmethod
    def get_user_teams(db: Client, user_id: str) -> list[dict[str, Any]]:
        """Fetch all teams a user belongs to."""
        teams_query = (
            db.collection("teams")
            .where("member_ids", "array_contains", user_id)
            .stream()
        )
        teams = []
        for doc in teams_query:
            data = doc.to_dict()
            if data:
                data["id"] = doc.id
                # Resolve partner
                member_ids = data.get("member_ids", [])
                partner_id = next((uid for uid in member_ids if uid != user_id), None)
                if partner_id:
                    data["partner_id"] = partner_id
                    partner_doc = db.collection("users").document(partner_id).get()
                    if partner_doc.exists:
                        data["partner"] = partner_doc.to_dict()
                teams.append(data)
        return teams
