"""Service layer for team-related operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from firebase_admin import firestore

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client


class TeamService:
    """Service class for team-related operations."""

    @staticmethod
    def get_or_create_team(db: Client, user_a_id: str, user_b_id: str) -> str:
        """Retrieves a team for two users, creating one if it doesn't exist."""
        # Sort IDs to ensure the query is consistent regardless of order
        member_ids = sorted([user_a_id, user_b_id])

        # Query for an existing team with the exact same members
        teams_ref = db.collection("teams")
        query = teams_ref.where(
            filter=firestore.FieldFilter("member_ids", "==", member_ids)
        )
        docs = list(query.stream())

        if docs:
            # Team already exists, return its ID
            return docs[0].id
        else:
            # Team does not exist, so create it
            user_a_ref = db.collection("users").document(user_a_id)
            user_b_ref = db.collection("users").document(user_b_id)

            user_a_doc = cast("DocumentSnapshot", user_a_ref.get())
            user_b_doc = cast("DocumentSnapshot", user_b_ref.get())

            user_a_data = user_a_doc.to_dict() or {}
            user_b_data = user_b_doc.to_dict() or {}

            user_a_name = user_a_data.get("name", "Player A")
            user_b_name = user_b_data.get("name", "Player B")

            new_team_data = {
                "member_ids": member_ids,
                "members": [user_a_ref, user_b_ref],
                "name": f"{user_a_name} & {user_b_name}",
                "stats": {"wins": 0, "losses": 0, "elo": 1200},
                "createdAt": firestore.SERVER_TIMESTAMP,
            }
            # Add the new team to the 'teams' collection
            new_team_ref = teams_ref.document()
            new_team_ref.set(new_team_data)
            return new_team_ref.id

    @staticmethod
    def migrate_user_teams(
        db: Client, batch: firestore.WriteBatch, source_id: str, target_id: str
    ) -> None:
        """Migrate all teams from source user to target user."""
        teams_query = (
            db.collection("teams")
            .where(
                filter=firestore.FieldFilter("member_ids", "array_contains", source_id)
            )
            .stream()
        )

        for team_doc in teams_query:
            team_data = team_doc.to_dict()
            if not team_data:
                continue

            member_ids = team_data.get("member_ids", [])
            new_member_ids = sorted(
                [target_id if mid == source_id else mid for mid in member_ids]
            )

            # Check if a team with the new member combination already exists
            existing_team_query = (
                db.collection("teams")
                .where(filter=firestore.FieldFilter("member_ids", "==", new_member_ids))
                .stream()
            )

            existing_teams = list(existing_team_query)
            # Remove current team from existing_teams
            existing_teams = [t for t in existing_teams if t.id != team_doc.id]

            if existing_teams:
                # Merge current team stats into existing team
                existing_team = cast("DocumentSnapshot", existing_teams[0])
                e_data = existing_team.to_dict() or {}

                t_stats: dict[str, Any] = team_data.get("stats", {})
                e_stats: dict[str, Any] = e_data.get("stats", {})

                new_wins = e_stats.get("wins", 0) + t_stats.get("wins", 0)
                new_losses = e_stats.get("losses", 0) + t_stats.get("losses", 0)

                batch.update(
                    existing_team.reference,
                    {"stats.wins": new_wins, "stats.losses": new_losses},
                )

                # Update matches to point to the existing team
                # This will be handled by match migration, but mark team for deletion
                batch.delete(team_doc.reference)
            else:
                # No existing team, just update the current team's members
                target_ref = db.collection("users").document(target_id)
                new_members = [
                    target_ref if m.id == source_id else m
                    for m in team_data.get("members", [])
                ]

                batch.update(
                    team_doc.reference,
                    {"member_ids": new_member_ids, "members": new_members},
                )
