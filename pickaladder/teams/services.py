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

    @staticmethod
    def get_team_dashboard_data(db: Client, team_id: str) -> dict[str, Any] | None:
        """Fetch all data required for the team dashboard."""
        team_ref = db.collection("teams").document(team_id)
        team = cast("DocumentSnapshot", team_ref.get())

        if not team.exists:
            return None

        team_data = team.to_dict() or {}
        team_data["id"] = team.id

        # Fetch members' data
        member_refs = team_data.get("members", [])
        members = []
        if member_refs:
            member_snapshots = db.get_all(member_refs)
            for snapshot in member_snapshots:
                shot = cast("DocumentSnapshot", snapshot)
                if shot.exists:
                    data = shot.to_dict() or {}
                    data["id"] = shot.id
                    members.append(data)

        # Fetch recent matches involving this team
        matches_ref = db.collection("matches")
        query1 = (
            matches_ref.where(filter=firestore.FieldFilter("team1Id", "==", team_id))
            .order_by("matchDate", direction=firestore.Query.DESCENDING)
            .limit(20)
        )
        query2 = (
            matches_ref.where(filter=firestore.FieldFilter("team2Id", "==", team_id))
            .order_by("matchDate", direction=firestore.Query.DESCENDING)
            .limit(20)
        )

        docs1 = list(query1.stream())
        docs2 = list(query2.stream())

        # Combine, remove duplicates, sort, and limit
        all_docs = {doc.id: doc for doc in docs1 + docs2}
        sorted_docs = sorted(
            all_docs.values(),
            key=lambda doc: (doc.to_dict() or {}).get(
                "matchDate", firestore.SERVER_TIMESTAMP
            ),
            reverse=True,
        )
        recent_matches_docs = sorted_docs[:20]

        # Batch fetch details for all opponent teams
        opponent_team_ids = set()
        for match_doc in recent_matches_docs:
            match_data = match_doc.to_dict() or {}
            if match_data.get("team1Id") == team_id:
                opponent_team_ids.add(match_data.get("team2Id"))
            else:
                opponent_team_ids.add(match_data.get("team1Id"))
        opponent_team_ids.discard(None)

        teams_map = {}
        if opponent_team_ids:
            id_list = list(opponent_team_ids)
            for i in range(0, len(id_list), 30):
                chunk = id_list[i : i + 30]
                team_docs = (
                    db.collection("teams")
                    .where(
                        filter=firestore.FieldFilter(
                            firestore.FieldPath.document_id(), "in", chunk
                        )
                    )
                    .stream()
                )
                for doc in team_docs:
                    teams_map[doc.id] = doc.to_dict()

        # Process matches for display
        recent_matches = []
        for match_doc in recent_matches_docs:
            match_data = match_doc.to_dict() or {}
            match_data["id"] = match_doc.id

            opponent_id = cast(
                str,
                match_data.get("team2Id")
                if match_data.get("team1Id") == team_id
                else match_data.get("team1Id"),
            )
            opponent_team_raw = teams_map.get(opponent_id) or {"name": "Unknown Team"}
            opponent_team = dict(opponent_team_raw)
            opponent_team["id"] = opponent_id
            match_data["opponent"] = opponent_team

            recent_matches.append(match_data)

        # Calculate aggregate stats
        stats = team_data.get("stats", {})
        wins = stats.get("wins", 0)
        losses = stats.get("losses", 0)
        total_games = wins + losses
        win_percentage = (wins / total_games) * 100 if total_games > 0 else 0

        # Calculate streak from sorted matches (newest to oldest)
        streak = 0
        streak_type = None
        if recent_matches:
            last_match = recent_matches[0]
            winner = last_match.get("winner")
            is_team1 = last_match.get("team1Id") == team_id
            if (winner == "team1" and is_team1) or (winner == "team2" and not is_team1):
                streak_type = "W"
            else:
                streak_type = "L"

            for match in recent_matches:
                winner = match.get("winner")
                is_team1 = match.get("team1Id") == team_id
                current_match_type = (
                    "W"
                    if (winner == "team1" and is_team1)
                    or (winner == "team2" and not is_team1)
                    else "L"
                )
                if current_match_type == streak_type:
                    streak += 1
                else:
                    break

        return {
            "team": team_data,
            "members": members,
            "recent_matches": recent_matches,
            "win_percentage": win_percentage,
            "streak": streak,
            "streak_type": streak_type,
        }
