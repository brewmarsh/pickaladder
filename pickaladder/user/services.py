"""Service layer for user data access and orchestration."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, cast

from firebase_admin import firestore
from flask import current_app

from .utils import smart_display_name

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client
    from google.cloud.firestore_v1.document import DocumentReference


class UserService:
    """Service class for user-related operations and Firestore interaction."""

    @staticmethod
    def get_user_by_id(db: Client, user_id: str) -> dict[str, Any] | None:
        """Fetch a user by their ID."""
        user_ref = db.collection("users").document(user_id)
        user_doc = cast("DocumentSnapshot", user_ref.get())
        if not user_doc.exists:
            return None
        data = user_doc.to_dict()
        if data is None:
            return None
        data["id"] = user_id
        return data

    @staticmethod
    def get_user_friends(
        db: Client, user_id: str, limit: int | None = None
    ) -> list[dict[str, Any]]:
        """Fetch a user's friends."""
        user_ref = db.collection("users").document(user_id)
        query = user_ref.collection("friends").where(
            filter=firestore.FieldFilter("status", "==", "accepted")
        )
        if limit:
            query = query.limit(limit)

        friends_query = query.stream()
        friend_ids = [f.id for f in friends_query]
        if not friend_ids:
            return []

        refs = [db.collection("users").document(fid) for fid in friend_ids]
        friend_docs = cast(list["DocumentSnapshot"], db.get_all(refs))
        results = []
        for doc in friend_docs:
            if doc.exists:
                data = doc.to_dict()
                if data is not None:
                    results.append({"id": doc.id, **data})
        return results

    @staticmethod
    def get_user_matches(db: Client, user_id: str) -> list[DocumentSnapshot]:
        """Fetch all matches involving a user."""
        user_ref = db.collection("users").document(user_id)
        matches_as_p1 = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("player1Ref", "==", user_ref))
            .stream()
        )
        matches_as_p2 = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("player2Ref", "==", user_ref))
            .stream()
        )
        matches_as_t1 = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("team1", "array_contains", user_ref))
            .stream()
        )
        matches_as_t2 = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("team2", "array_contains", user_ref))
            .stream()
        )

        all_matches = (
            list(matches_as_p1)
            + list(matches_as_p2)
            + list(matches_as_t1)
            + list(matches_as_t2)
        )
        unique_matches = {match.id: match for match in all_matches}.values()
        return list(unique_matches)

    @staticmethod
    def merge_ghost_account(db: Client, real_user_ref: Any, email: str) -> bool:
        """Check for 'ghost' user with the given email and merge their data."""
        try:
            query = (
                db.collection("users")
                .where(filter=firestore.FieldFilter("email", "==", email.lower()))
                .where(filter=firestore.FieldFilter("is_ghost", "==", True))
                .limit(1)
            )

            ghost_docs = list(query.stream())
            if not ghost_docs:
                return False

            ghost_doc = ghost_docs[0]
            current_app.logger.info(
                f"Merging ghost user {ghost_doc.id} to {real_user_ref.id}"
            )

            batch = db.batch()
            UserService._migrate_ghost_references(
                db, batch, ghost_doc.reference, real_user_ref
            )
            batch.delete(ghost_doc.reference)
            batch.commit()
            current_app.logger.info("Ghost user merge completed successfully.")
            return True

        except Exception as e:
            current_app.logger.error(f"Error merging ghost user: {e}")
            return False

    @staticmethod
    def _migrate_ghost_references(
        db: Client, batch: firestore.WriteBatch, ghost_ref: Any, real_user_ref: Any
    ) -> None:
        """Update all Firestore references from a ghost user to a real user."""
        # 1 & 2: Update Singles Matches
        for field in ["player1Ref", "player2Ref"]:
            for match in (
                db.collection("matches")
                .where(filter=firestore.FieldFilter(field, "==", ghost_ref))
                .stream()
            ):
                batch.update(match.reference, {field: real_user_ref})

        # 3 & 4: Update Doubles Matches
        for field in ["team1", "team2"]:
            for match in (
                db.collection("matches")
                .where(filter=firestore.FieldFilter(field, "array_contains", ghost_ref))
                .stream()
            ):
                batch.update(
                    match.reference, {field: firestore.ArrayRemove([ghost_ref])}
                )
                batch.update(
                    match.reference, {field: firestore.ArrayUnion([real_user_ref])}
                )

        # 5: Update Group Memberships
        groups_query = db.collection("groups").where(
            filter=firestore.FieldFilter("members", "array_contains", ghost_ref)
        )
        for group in groups_query.stream():
            batch.update(
                group.reference, {"members": firestore.ArrayRemove([ghost_ref])}
            )
            batch.update(
                group.reference, {"members": firestore.ArrayUnion([real_user_ref])}
            )

        # 6: Update Tournament Participants
        tournaments_query = db.collection("tournaments").where(
            filter=firestore.FieldFilter(
                "participant_ids", "array_contains", ghost_ref.id
            )
        )
        for tournament in tournaments_query.stream():
            data = tournament.to_dict()
            if not data:
                continue
            participants = data.get("participants", [])
            updated = False
            for p in participants:
                p_uid = None
                if "userRef" in p:
                    p_uid = p["userRef"].id
                elif "user_id" in p:
                    p_uid = p["user_id"]

                if p_uid == ghost_ref.id:
                    p["userRef"] = real_user_ref
                    p["user_id"] = real_user_ref.id
                    updated = True

            if updated:
                p_ids = data.get("participant_ids", [])
                new_p_ids = [
                    real_user_ref.id if pid == ghost_ref.id else pid for pid in p_ids
                ]
                batch.update(
                    tournament.reference,
                    {"participants": participants, "participant_ids": new_p_ids},
                )

    @staticmethod
    def get_user_groups(db: Client, user_id: str) -> list[dict[str, Any]]:
        """Fetch all groups the user is a member of."""
        user_ref = db.collection("users").document(user_id)
        groups_query = (
            db.collection("groups")
            .where(filter=firestore.FieldFilter("members", "array_contains", user_ref))
            .stream()
        )
        groups = []
        for doc in groups_query:
            data = doc.to_dict()
            if data:
                data["id"] = doc.id
                groups.append(data)
        return groups

    @staticmethod
    def _get_player_info(
        player_ref: DocumentReference, users_map: dict[str, Any]
    ) -> dict[str, Any]:
        """Return a dictionary with player info."""
        player_data = users_map.get(player_ref.id)
        if not player_data:
            return {"id": player_ref.id, "username": "Unknown", "thumbnail_url": ""}
        return {
            "id": player_ref.id,
            "username": smart_display_name(player_data),
            "thumbnail_url": player_data.get("thumbnail_url", ""),
        }

    @staticmethod
    def _get_match_winner_slot(match_data: dict[str, Any]) -> str:
        """Determine the winner slot of a match."""
        p1_score = match_data.get("player1Score", 0)
        p2_score = match_data.get("player2Score", 0)
        return "player1" if p1_score > p2_score else "player2"

    @staticmethod
    def _get_user_match_result(
        match_data: dict[str, Any], user_id: str, winner: str
    ) -> str:
        """Determine if the user won, lost, or drew the match."""
        p1_score = match_data.get("player1Score", 0)
        p2_score = match_data.get("player2Score", 0)
        if p1_score == p2_score:
            return "draw"

        user_won = False
        if match_data.get("matchType") == "doubles":
            team1_refs = match_data.get("team1", [])
            in_team1 = any(ref.id == user_id for ref in team1_refs)
            if (in_team1 and winner == "player1") or (not in_team1 and winner == "player2"):
                user_won = True
        else:
            p1_ref = match_data.get("player1Ref")
            is_p1 = p1_ref and p1_ref.id == user_id
            if (is_p1 and winner == "player1") or (not is_p1 and winner == "player2"):
                user_won = True
        return "win" if user_won else "loss"

    @staticmethod
    def _collect_match_refs(
        matches_docs: list[DocumentSnapshot],
    ) -> tuple[set[DocumentReference], set[DocumentReference]]:
        """Collect all unique user and team references from match documents."""
        player_refs = set()
        team_refs = set()
        for match_doc in matches_docs:
            match = match_doc.to_dict()
            if match is None:
                continue
            if match.get("player1Ref"):
                player_refs.add(match["player1Ref"])
            if match.get("player2Ref"):
                player_refs.add(match["player2Ref"])
            player_refs.update(match.get("team1", []))
            player_refs.update(match.get("team2", []))
            if match.get("team1Ref"):
                team_refs.add(match["team1Ref"])
            if match.get("team2Ref"):
                team_refs.add(match["team2Ref"])
        return player_refs, team_refs

    @staticmethod
    def _fetch_match_entities(
        db: Client, matches_docs: list[DocumentSnapshot]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Fetch all users and teams involved in a list of matches."""
        player_refs, team_refs = UserService._collect_match_refs(matches_docs)
        users_map = {}
        if player_refs:
            user_docs = db.get_all(list(player_refs))
            users_map = {doc.id: doc.to_dict() for doc in user_docs if doc.exists}
        teams_map = {}
        if team_refs:
            team_docs = db.get_all(list(team_refs))
            teams_map = {doc.id: doc.to_dict() for doc in team_docs if doc.exists}
        return users_map, teams_map

    @staticmethod
    def format_matches_for_dashboard(
        db: Client, matches_docs: list[DocumentSnapshot], user_id: str
    ) -> list[dict[str, Any]]:
        """Enrich match documents with user and team data for dashboard display."""
        users_map, teams_map = UserService._fetch_match_entities(db, matches_docs)

        # Batch fetch tournament names
        tournament_ids = {m.to_dict().get("tournamentId") for m in matches_docs if m.to_dict() and m.to_dict().get("tournamentId")}
        tournaments_map = {}
        if tournament_ids:
            tournament_refs = [db.collection("tournaments").document(tid) for tid in tournament_ids if tid]
            tournament_docs = db.get_all(tournament_refs)
            tournaments_map = {doc.id: doc.to_dict() for doc in tournament_docs if doc.exists}

        matches_data = []
        for match_doc in matches_docs:
            m_data = match_doc.to_dict()
            if m_data is None:
                continue

            winner = UserService._get_match_winner_slot(m_data)
            user_result = UserService._get_user_match_result(m_data, user_id, winner)

            if m_data.get("matchType") == "doubles":
                p1_info = [UserService._get_player_info(r, users_map) for r in m_data.get("team1", [])]
                p2_info = [UserService._get_player_info(r, users_map) for r in m_data.get("team2", [])]
            else:
                p1_info = UserService._get_player_info(m_data["player1Ref"], users_map)
                p2_info = UserService._get_player_info(m_data["player2Ref"], users_map)

            t1_name = teams_map.get(m_data["team1Ref"].id, {}).get("name", "Team 1") if m_data.get("team1Ref") else "Team 1"
            t2_name = teams_map.get(m_data["team2Ref"].id, {}).get("name", "Team 2") if m_data.get("team2Ref") else "Team 2"
            t_name = tournaments_map.get(m_data.get("tournamentId"), {}).get("name")

            matches_data.append({
                "id": match_doc.id,
                "player1": p1_info,
                "player2": p2_info,
                "player1_score": m_data.get("player1Score", 0),
                "player2_score": m_data.get("player2Score", 0),
                "winner": winner,
                "date": m_data.get("matchDate", "N/A"),
                "is_group_match": bool(m_data.get("groupId")),
                "match_type": m_data.get("matchType", "singles"),
                "user_result": user_result,
                "team1_name": t1_name,
                "team2_name": t2_name,
                "tournament_name": t_name,
            })
        return matches_data