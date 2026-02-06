"""Service layer for user data access and orchestration."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, cast

from firebase_admin import firestore
from flask import current_app

from .helpers import smart_display_name

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
        """Helper to update all Firestore references from a ghost user to a real user."""
        # 1 & 2: Update Singles Matches
        for field in ["player1Ref", "player2Ref"]:
            for match in (
                db.collection("matches")
                .where(filter=firestore.FieldFilter(field, "==", ghost_ref))
                .stream()
            ):
                batch.update(match.reference, {field: real_user_ref})

        # 3 & 4: Update Doubles Matches (Array fields)
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
                # Handle both userRef (object) and user_id (string) formats
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
    def get_friendship_info(
        db: Client, current_user_id: str, target_user_id: str
    ) -> tuple[bool, bool]:
        """Check friendship status between two users."""
        friend_request_sent = is_friend = False
        if current_user_id != target_user_id:
            friend_ref = (
                db.collection("users")
                .document(current_user_id)
                .collection("friends")
                .document(target_user_id)
            )
            friend_doc = friend_ref.get()
            if friend_doc.exists:
                status = friend_doc.to_dict().get("status")
                if status == "accepted":
                    is_friend = True
                elif status == "pending":
                    friend_request_sent = True
        return is_friend, friend_request_sent

    @staticmethod
    def get_user_pending_requests(db: Client, user_id: str) -> list[dict[str, Any]]:
        """Fetch pending friend requests where the user is the recipient."""
        user_ref = db.collection("users").document(user_id)
        requests_query = (
            user_ref.collection("friends")
            .where(filter=firestore.FieldFilter("status", "==", "pending"))
            .where(filter=firestore.FieldFilter("initiator", "==", False))
            .stream()
        )
        request_ids = [doc.id for doc in requests_query]
        if not request_ids:
            return []

        refs = [db.collection("users").document(uid) for uid in request_ids]
        request_docs = cast(list["DocumentSnapshot"], db.get_all(refs))
        results = []
        for doc in request_docs:
            if doc.exists:
                data = doc.to_dict()
                if data is not None:
                    results.append({"id": doc.id, **data})
        return results

    @staticmethod
    def get_pending_tournament_invites(
        db: Client, user_id: str
    ) -> list[dict[str, Any]]:
        """Fetch pending tournament invites for a user."""
        tournaments_query = (
            db.collection("tournaments")
            .where(
                filter=firestore.FieldFilter(
                    "participant_ids", "array_contains", user_id
                )
            )
            .stream()
        )

        pending_invites = []
        for doc in tournaments_query:
            data = doc.to_dict()
            if data:
                participants = data.get("participants", [])
                for p in participants:
                    p_uid = p.get("userRef").id if "userRef" in p else p.get("user_id")
                    if p_uid == user_id and p["status"] == "pending":
                        data["id"] = doc.id
                        pending_invites.append(data)
                        break
        return pending_invites

    @staticmethod
    def get_active_tournaments(db: Client, user_id: str) -> list[dict[str, Any]]:
        """Fetch active tournaments for a user."""
        tournaments_query = (
            db.collection("tournaments")
            .where(
                filter=firestore.FieldFilter(
                    "participant_ids", "array_contains", user_id
                )
            )
            .stream()
        )
        active_tournaments = []
        for doc in tournaments_query:
            data = doc.to_dict()
            if data and data.get("status") in ["Active", "Scheduled"]:
                participants = data.get("participants") or []
                for p in participants:
                    if not p:
                        continue
                    p_uid = (
                        p.get("userRef").id if p.get("userRef") else p.get("user_id")
                    )
                    if p_uid == user_id and p.get("status") == "accepted":
                        data["id"] = doc.id
                        # Format date for display
                        raw_date = data.get("date")
                        if raw_date is not None:
                            if hasattr(raw_date, "to_datetime"):
                                data["date_display"] = raw_date.to_datetime().strftime(
                                    "%b %d, %Y"
                                )
                            elif isinstance(raw_date, datetime.datetime):
                                data["date_display"] = raw_date.strftime("%b %d, %Y")
                        active_tournaments.append(data)
                        break
        return active_tournaments

    @staticmethod
    def get_past_tournaments(db: Client, user_id: str) -> list[dict[str, Any]]:
        """Fetch past (completed) tournaments for a user."""
        from pickaladder.tournament.utils import (  # noqa: PLC0415
            get_tournament_standings,
        )

        tournaments_query = (
            db.collection("tournaments")
            .where(
                filter=firestore.FieldFilter(
                    "participant_ids", "array_contains", user_id
                )
            )
            .stream()
        )
        past_tournaments = []
        for doc in tournaments_query:
            data = doc.to_dict()
            if data and data.get("status") == "Completed":
                data["id"] = doc.id
                # Find winner
                match_type = data.get("matchType", "singles")
                standings = get_tournament_standings(db, doc.id, match_type)
                data["winner_name"] = standings[0]["name"] if standings else "TBD"

                raw_date = data.get("date")
                if raw_date is not None:
                    if hasattr(raw_date, "to_datetime"):
                        data["date_display"] = raw_date.to_datetime().strftime(
                            "%b %d, %Y"
                        )
                    elif isinstance(raw_date, datetime.datetime):
                        data["date_display"] = raw_date.strftime("%b %d, %Y")

                past_tournaments.append(data)

        # Sort by date descending
        past_tournaments.sort(
            key=lambda x: x.get("date") or datetime.datetime.min, reverse=True
        )
        return past_tournaments

    @staticmethod
    def get_user_sent_requests(db: Client, user_id: str) -> list[dict[str, Any]]:
        """Fetch pending friend requests where the user is the initiator."""
        user_ref = db.collection("users").document(user_id)
        requests_query = (
            user_ref.collection("friends")
            .where(filter=firestore.FieldFilter("status", "==", "pending"))
            .where(filter=firestore.FieldFilter("initiator", "==", True))
            .stream()
        )
        request_ids = [doc.id for doc in requests_query]
        if not request_ids:
            return []

        refs = [db.collection("users").document(uid) for uid in request_ids]
        request_docs = cast(list["DocumentSnapshot"], db.get_all(refs))
        results = []
        for doc in request_docs:
            if doc.exists:
                data = doc.to_dict()
                if data is not None:
                    results.append({"id": doc.id, **data})
        return results

    @staticmethod
    def get_all_users(
        db: Client, exclude_user_id: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Fetch a list of users, excluding the current user, sorted by date."""
        users_query = (
            db.collection("users")
            .order_by("createdAt", direction=firestore.Query.DESCENDING)
            .limit(limit + 1)  # Fetch one extra in case we exclude the current user
            .stream()
        )
        users = []
        for doc in users_query:
            if doc.id == exclude_user_id:
                continue
            data = doc.to_dict()
            if data is not None:
                data["id"] = doc.id
                users.append(data)
            if len(users) >= limit:
                break
        return users

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
            if (in_team1 and winner == "player1") or (
                not in_team1 and winner == "player2"
            ):
                user_won = True
        else:
            p1_ref = match_data.get("player1Ref")
            is_player1 = p1_ref and p1_ref.id == user_id
            if (is_player1 and winner == "player1") or (
                not is_player1 and winner == "player2"
            ):
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
    def _get_profile_match_alignment(
        data: dict[str, Any],
        user_id: str,
        profile_username: str,
        users_map: dict[str, Any],
    ) -> dict[str, Any]:
        """Align match data so the profile user is in the expected slot for UI."""
        match_type = data.get("matchType", "singles")
        p1_info = {"username": "Unknown"}
        p2_info = {"id": "", "username": "Unknown"}
        p1_id = ""

        if match_type == "doubles":
            team1_refs = data.get("team1", [])
            team2_refs = data.get("team2", [])
            in_team1 = any(ref.id == user_id for ref in team1_refs)
            opp_refs = team2_refs if in_team1 else team1_refs

            opp_name = "Unknown Team"
            opp_id = ""
            if opp_refs:
                opp_ref = opp_refs[0]
                opp_id = opp_ref.id
                opp_name = users_map.get(opp_id, {}).get("username", "Unknown")
                if len(team1_refs) > 1 or len(team2_refs) > 1:
                    opp_name += " (Doubles)"

            if in_team1:
                p1_id, p1_info = user_id, {"id": user_id, "username": profile_username}
                p2_info = {"id": opp_id, "username": opp_name}
            else:
                p1_info = {"id": opp_id, "username": opp_name}
                p2_info = {"id": user_id, "username": profile_username}
        else:
            p1_ref = data.get("player1Ref")
            p2_ref = data.get("player2Ref")
            if p1_ref and p1_ref.id == user_id:
                p1_id, p1_info = user_id, {"id": user_id, "username": profile_username}
                opp_ref = p2_ref
                p2_info = {
                    "id": opp_ref.id if opp_ref else "",
                    "username": users_map.get(opp_ref.id, {}).get("username", "Unknown")
                    if opp_ref
                    else "Unknown",
                }
            else:
                p1_id = p1_ref.id if p1_ref else ""
                p1_info = {
                    "id": p1_id,
                    "username": users_map.get(p1_id, {}).get("username", "Unknown")
                    if p1_id
                    else "Unknown",
                }
                p2_info = {"id": user_id, "username": profile_username}

        return {"player1_id": p1_id, "player1": p1_info, "player2": p2_info}

    @staticmethod
    def format_matches_for_profile(
        db: Client,
        display_items: list[dict[str, Any]],
        user_id: str,
        profile_user_data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Format matches for the public profile view with consistent alignment."""
        matches_docs = [item["doc"] for item in display_items]
        users_map, _ = UserService._fetch_match_entities(db, matches_docs)
        profile_username = profile_user_data.get("username", "Unknown")
        final_matches = []

        for item in display_items:
            data = item["data"]
            alignment = UserService._get_profile_match_alignment(
                data, user_id, profile_username, users_map
            )

            final_matches.append(
                {
                    "id": item["doc"].id,
                    "match_date": data.get("matchDate"),
                    "player1_score": data.get("player1Score", 0),
                    "player2_score": data.get("player2Score", 0),
                    **alignment,
                }
            )
        return final_matches

    @staticmethod
    def get_public_groups(db: Client, limit: int = 10) -> list[dict[str, Any]]:
        """Fetch a list of public groups, enriched with owner data."""
        # Query for public groups
        public_groups_query = (
            db.collection("groups")
            .where(filter=firestore.FieldFilter("is_public", "==", True))
            .order_by("createdAt", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        public_group_docs = list(public_groups_query.stream())

        # Enrich groups with owner data
        owner_refs = []
        for doc in public_group_docs:
            data = doc.to_dict()
            if data and (ref := data.get("ownerRef")):
                owner_refs.append(ref)
        unique_owner_refs = list({ref for ref in owner_refs if ref})

        owners_data = {}
        if unique_owner_refs:
            owner_docs = db.get_all(unique_owner_refs)
            owners_data = {doc.id: doc.to_dict() for doc in owner_docs if doc.exists}

        guest_user = {"username": "Guest", "id": "unknown"}

        enriched_groups = []
        for doc in public_group_docs:
            data = doc.to_dict()
            if data is None:
                continue
            data["id"] = doc.id
            owner_ref = data.get("ownerRef")
            if owner_ref and owner_ref.id in owners_data:
                data["owner"] = owners_data[owner_ref.id]
            else:
                data["owner"] = guest_user
            enriched_groups.append(data)

        return enriched_groups

    @staticmethod
    def format_matches_for_dashboard(
        db: Client, matches_docs: list[DocumentSnapshot], user_id: str
    ) -> list[dict[str, Any]]:
        """Enrich match documents with user and team data for dashboard display."""
        users_map, teams_map = UserService._fetch_match_entities(db, matches_docs)

        # Batch fetch tournament names
        tournament_ids = set()
        for m in matches_docs:
            m_data = m.to_dict()
            if m_data and (tid := m_data.get("tournamentId")):
                tournament_ids.add(tid)
        tournaments_map: dict[str, dict[str, Any]] = {}
        if tournament_ids:
            tournament_refs = [
                db.collection("tournaments").document(tid)
                for tid in tournament_ids
                if tid
            ]
            tournament_docs = db.get_all(tournament_refs)
            for doc in tournament_docs:
                if doc.exists and (d := doc.to_dict()):
                    tournaments_map[doc.id] = d

        matches_data = []

        for match_doc in matches_docs:
            m_data = match_doc.to_dict()
            if m_data is None:
                continue
            match_dict: dict[str, Any] = m_data

            winner = UserService._get_match_winner_slot(match_dict)
            user_result = UserService._get_user_match_result(
                match_dict, user_id, winner
            )

            p1_info: dict[str, Any] | list[dict[str, Any]]
            p2_info: dict[str, Any] | list[dict[str, Any]]

            if match_dict.get("matchType") == "doubles":
                p1_info = [
                    UserService._get_player_info(r, users_map)
                    for r in match_dict.get("team1", [])
                ]
                p2_info = [
                    UserService._get_player_info(r, users_map)
                    for r in match_dict.get("team2", [])
                ]
            else:
                p1_info = UserService._get_player_info(
                    match_dict["player1Ref"], users_map
                )
                p2_info = UserService._get_player_info(
                    match_dict["player2Ref"], users_map
                )

            t1_name = "Team 1"
            t2_name = "Team 2"
            if t1_ref := match_dict.get("team1Ref"):
                t1_name = teams_map.get(t1_ref.id, {}).get("name", "Team 1")
            if t2_ref := match_dict.get("team2Ref"):
                t2_name = teams_map.get(t2_ref.id, {}).get("name", "Team 2")

            tournament_name = None
            if t_id := match_dict.get("tournamentId"):
                tournament_name = tournaments_map.get(t_id, {}).get("name")

            matches_data.append(
                {
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
                    "tournament_name": tournament_name,
                }
            )
        return matches_data
