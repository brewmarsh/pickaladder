from __future__ import annotations

"""Service layer for team-related operations."""


from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from firebase_admin import firestore
from google.cloud.firestore_v1.field_path import FieldPath

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
                .where("member_ids", "==", new_member_ids)
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

        # Decomposed calls with efficient data passing
        members = TeamService._fetch_team_members(db, team_data)
        recent_matches = TeamService._fetch_team_matches(db, team_id)
        stats = TeamService._calculate_team_stats(team_id, team_data, recent_matches)

        return {
            "team": team_data,
            "members": members,
            "recent_matches": recent_matches,
            "win_percentage": stats.get("win_percentage", 0),
            "streak": stats.get("streak", 0),
            "streak_type": stats.get("streak_type"),
        }

    @staticmethod
    def _fetch_team_members(
        db: Client, team_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Fetch member data from team references."""
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
        return members

    @staticmethod
    def _get_opponent_team_ids(matches: list[Any], team_id: str) -> set[str]:
        """Extract unique opponent team IDs from a list of matches."""
        opp_ids = set()
        for match in matches:
            data = match.to_dict() or {}
            t1_id, t2_id = data.get("team1Id"), data.get("team2Id")
            opp_ids.add(t2_id if t1_id == team_id else t1_id)
        return {str(oid) for oid in opp_ids if oid is not None}

    @staticmethod
    def _fetch_opponent_teams_map(db: Client, opponent_ids: set[str]) -> dict[str, Any]:
        """Fetch opponent teams from Firestore and return a map."""
        teams_map = {}
        id_list = list(opponent_ids)
        for i in range(0, len(id_list), 30):
            chunk = id_list[i : i + 30]
            query = db.collection("teams").where(
                filter=firestore.FieldFilter(FieldPath.document_id(), "in", chunk)
            )
            for doc in query.stream():
                teams_map[doc.id] = doc.to_dict()
        return teams_map

    @staticmethod
    def _enrich_team_match_data(
        match_doc: Any, team_id: str, teams_map: dict[str, Any]
    ) -> dict[str, Any]:
        """Attach opponent details to a single match data dictionary."""
        data = match_doc.to_dict() or {}
        data["id"] = match_doc.id

        opp_id = (
            data.get("team2Id")
            if data.get("team1Id") == team_id
            else data.get("team1Id")
        )
        opp_raw = teams_map.get(cast(str, opp_id)) or {"name": "Unknown Team"}

        opponent = dict(opp_raw)
        opponent["id"] = opp_id
        data["opponent"] = opponent
        return data

    @staticmethod
    def _fetch_team_matches(db: Client, team_id: str) -> list[dict[str, Any]]:
        """Fetch recent matches and opponent details for a team."""
        matches_ref = db.collection("matches")
        q1 = matches_ref.where("team1Id", "==", team_id)
        q2 = matches_ref.where("team2Id", "==", team_id)

        all_docs = {d.id: d for d in list(q1.stream()) + list(q2.stream())}
        sorted_docs = sorted(
            all_docs.values(),
            key=lambda d: (d.to_dict() or {}).get("matchDate", datetime.min),
            reverse=True,
        )[:20]

        opp_ids = TeamService._get_opponent_team_ids(sorted_docs, team_id)
        teams_map = TeamService._fetch_opponent_teams_map(db, opp_ids)

        return [
            TeamService._enrich_team_match_data(doc, team_id, teams_map)
            for doc in sorted_docs
        ]

    @staticmethod
    def _calculate_team_stats(
        team_id: str, team_data: dict[str, Any], matches: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Calculate win percentage and streak information."""
        stats = team_data.get("stats", {})
        wins = stats.get("wins", 0)
        losses = stats.get("losses", 0)
        total_games = wins + losses
        win_percentage = (wins / total_games) * 100 if total_games > 0 else 0

        # Calculate streak from sorted matches (newest to oldest)
        streak = 0
        streak_type = None
        if matches:
            last_match = matches[0]
            winner = last_match.get("winner")
            is_team1 = last_match.get("team1Id") == team_id
            if (winner == "team1" and is_team1) or (winner == "team2" and not is_team1):
                streak_type = "W"
            else:
                streak_type = "L"

            for match in matches:
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
            "wins": wins,
            "losses": losses,
            "win_percentage": win_percentage,
            "streak": streak,
            "streak_type": streak_type,
        }
