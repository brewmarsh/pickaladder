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

    from pickaladder.group.models import Group
    from pickaladder.match.models import Match
    from pickaladder.tournament.models import Tournament

    from .models import User, UserRanking, UserStats


class UserService:
    """Service class for user-related operations and Firestore interaction."""

    @staticmethod
    def smart_display_name(user: User | dict[str, Any]) -> str:
        """Return a smart display name for a user."""
        return smart_display_name(user)

    @staticmethod
    def update_user_profile(
        db: Client, user_id: str, update_data: User | dict[str, Any]
    ) -> None:
        """Update a user's profile in Firestore."""
        user_ref = db.collection("users").document(user_id)
        user_ref.update(cast("dict[Any, Any]", update_data))

    @staticmethod
    def get_user_by_id(db: Client, user_id: str) -> User | None:
        """Fetch a user by their ID."""
        user_ref = db.collection("users").document(user_id)
        user_doc = cast("DocumentSnapshot", user_ref.get())
        if not user_doc.exists:
            return None
        data = cast("User", user_doc.to_dict())
        if data is None:
            return None
        data["id"] = user_id
        return data

    @staticmethod
    def get_user_friends(
        db: Client, user_id: str, limit: int | None = None
    ) -> list[User]:
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
        results: list[User] = []
        for doc in friend_docs:
            if doc.exists:
                data = doc.to_dict()
                if data is not None:
                    user_data = cast("User", data)
                    user_data["id"] = doc.id
                    results.append(user_data)
        return results

    @staticmethod
    def get_user_matches(db: Client, user_id: str) -> list[Match]:
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
        results: list[Match] = []
        for match in unique_matches:
            data = cast("Match", match.to_dict() or {})
            data["id"] = match.id
            results.append(data)
        return results

    @staticmethod
    def merge_ghost_user(db: Client, real_user_ref: Any, email: str) -> bool:
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

            UserService.merge_users(db, ghost_doc.id, real_user_ref.id)
            current_app.logger.info("Ghost user merge completed successfully.")
            return True

        except Exception as e:
            current_app.logger.error(f"Error merging ghost user: {e}")
            return False

    @staticmethod
    def merge_users(db: Client, source_id: str, target_id: str) -> None:
        """Perform a deep merge of two user accounts. Source is deleted."""
        from pickaladder.teams.services import TeamService  # noqa: PLC0415

        source_ref = db.collection("users").document(source_id)
        target_ref = db.collection("users").document(target_id)

        batch = db.batch()
        UserService._migrate_ghost_references(db, batch, source_ref, target_ref)
        TeamService.migrate_user_teams(db, batch, source_id, target_id)
        batch.delete(source_ref)
        batch.commit()

    @staticmethod
    def _migrate_ghost_references(
        db: Client, batch: firestore.WriteBatch, ghost_ref: Any, real_user_ref: Any
    ) -> None:
        """Orchestrate the migration of all ghost user references."""
        UserService._migrate_singles_matches(db, batch, ghost_ref, real_user_ref)
        UserService._migrate_doubles_matches(db, batch, ghost_ref, real_user_ref)
        UserService._migrate_groups(db, batch, ghost_ref, real_user_ref)
        UserService._migrate_tournaments(db, batch, ghost_ref, real_user_ref)

    @staticmethod
    def _migrate_singles_matches(
        db: Client, batch: firestore.WriteBatch, ghost_ref: Any, real_user_ref: Any
    ) -> None:
        """Update singles matches where the ghost user is player 1 or 2."""
        match_updates: dict[str, dict[str, Any]] = {}
        for field in ["player1Ref", "player2Ref"]:
            matches = (
                db.collection("matches")
                .where(filter=firestore.FieldFilter(field, "==", ghost_ref))
                .stream()
            )
            for match in matches:
                if match.id not in match_updates:
                    match_updates[match.id] = {"ref": match.reference, "data": {}}
                match_updates[match.id]["data"][field] = real_user_ref

        for update in match_updates.values():
            batch.update(update["ref"], update["data"])

    @staticmethod
    def _migrate_doubles_matches(
        db: Client, batch: firestore.WriteBatch, ghost_ref: Any, real_user_ref: Any
    ) -> None:
        """Update doubles matches where the ghost user is in a team array."""
        from pickaladder.teams.services import TeamService  # noqa: PLC0415

        match_updates: dict[str, dict[str, Any]] = {}
        for field in ["team1", "team2"]:
            matches = (
                db.collection("matches")
                .where(filter=firestore.FieldFilter(field, "array_contains", ghost_ref))
                .stream()
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
                    partner_ref = next(
                        (r for r in current_team if r != ghost_ref), None
                    )
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

    @staticmethod
    def _migrate_groups(
        db: Client, batch: firestore.WriteBatch, ghost_ref: Any, real_user_ref: Any
    ) -> None:
        """Update group memberships."""
        groups = (
            db.collection("groups")
            .where(filter=firestore.FieldFilter("members", "array_contains", ghost_ref))
            .stream()
        )
        for group in groups:
            g_data = group.to_dict()
            if g_data and "members" in g_data:
                current_members = g_data["members"]
                new_members = [
                    real_user_ref if m == ghost_ref else m for m in current_members
                ]
                batch.update(group.reference, {"members": new_members})

    @staticmethod
    def _migrate_tournaments(
        db: Client, batch: firestore.WriteBatch, ghost_ref: Any, real_user_ref: Any
    ) -> None:
        """Update tournament participant lists and IDs."""
        tournaments = (
            db.collection("tournaments")
            .where(
                filter=firestore.FieldFilter(
                    "participant_ids", "array_contains", ghost_ref.id
                )
            )
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
                p_uid = getattr(p_ref, "id", None) if p_ref else p.get("user_id")

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

    @staticmethod
    def get_user_groups(db: Client, user_id: str) -> list[Group]:
        """Fetch all groups the user is a member of."""
        user_ref = db.collection("users").document(user_id)
        groups_query = (
            db.collection("groups")
            .where(filter=firestore.FieldFilter("members", "array_contains", user_ref))
            .stream()
        )
        groups: list[Group] = []
        for doc in groups_query:
            data = cast("Group", doc.to_dict())
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
                data = friend_doc.to_dict()
                if data:
                    status = data.get("status")
                    if status == "accepted":
                        is_friend = True
                    elif status == "pending":
                        friend_request_sent = True
        return is_friend, friend_request_sent

    @staticmethod
    def get_user_pending_requests(db: Client, user_id: str) -> list[User]:
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
        results: list[User] = []
        for doc in request_docs:
            if doc.exists:
                data = doc.to_dict()
                if data is not None:
                    user_data = cast("User", data)
                    user_data["id"] = doc.id
                    results.append(user_data)
        return results

    @staticmethod
    def get_pending_tournament_invites(db: Client, user_id: str) -> list[Tournament]:
        """Fetch pending tournament invites for a user."""
        if not user_id:
            return []
        try:
            tournaments_query = (
                db.collection("tournaments")
                .where(
                    filter=firestore.FieldFilter(
                        "participant_ids", "array_contains", user_id
                    )
                )
                .stream()
            )

            pending_invites: list[Tournament] = []
            for doc in tournaments_query:
                data = cast("Tournament", doc.to_dict())
                if data:
                    participants = data.get("participants") or []
                    for p in participants:
                        if not p:
                            continue
                        p_ref = p.get("userRef")
                        p_uid = (
                            getattr(p_ref, "id", None) if p_ref else p.get("user_id")
                        )
                        if p_uid == user_id and p.get("status") == "pending":
                            data["id"] = doc.id
                            pending_invites.append(data)
                            break
            return pending_invites
        except TypeError:
            # Handle mockfirestore bug when array field is None
            return []

    @staticmethod
    def get_active_tournaments(db: Client, user_id: str) -> list[Tournament]:
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
        active_tournaments: list[Tournament] = []
        for doc in tournaments_query:
            data = cast("Tournament", doc.to_dict())
            if data and data.get("status") in ["Active", "Scheduled"]:
                participants = data.get("participants") or []
                for p in participants:
                    if not p:
                        continue
                    p_uid = (
                        getattr(p.get("userRef"), "id", None)
                        if p.get("userRef")
                        else p.get("user_id")
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
        # Sort by date ascending (soonest first)
        active_tournaments.sort(key=lambda x: x.get("date") or datetime.datetime.max)
        return active_tournaments

    @staticmethod
    def get_past_tournaments(db: Client, user_id: str) -> list[Tournament]:
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
        past_tournaments: list[Tournament] = []
        for doc in tournaments_query:
            data = cast("Tournament", doc.to_dict())
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
    def get_user_sent_requests(db: Client, user_id: str) -> list[User]:
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
        results: list[User] = []
        for doc in request_docs:
            if doc.exists:
                data = doc.to_dict()
                if data is not None:
                    user_data = cast("User", data)
                    user_data["id"] = doc.id
                    results.append(user_data)
        return results

    @staticmethod
    def get_all_users(
        db: Client, exclude_ids: list[str] | None = None, limit: int = 20
    ) -> list[User]:
        """Fetch a list of users, excluding given IDs, sorted by date."""
        if exclude_ids is None:
            exclude_ids = []

        users_query = (
            db.collection("users")
            .order_by("createdAt", direction=firestore.Query.DESCENDING)
            .limit(limit + len(exclude_ids))  # Fetch extra in case we exclude users
            .stream()
        )
        users: list[User] = []
        for doc in users_query:
            if exclude_ids and doc.id in exclude_ids:
                continue
            data = doc.to_dict()
            if data is not None:
                user_data = cast("User", data)
                user_data["id"] = doc.id
                users.append(user_data)
            if len(users) >= limit:
                break
        return users

    @staticmethod
    def _get_player_info(player_ref: Any, users_map: dict[str, Any]) -> dict[str, Any]:
        """Return a dictionary with player info."""
        player_data = users_map.get(player_ref.id)
        if not player_data:
            return {"id": player_ref.id, "username": "Unknown", "thumbnail_url": ""}
        return {
            "id": player_ref.id,
            "username": UserService.smart_display_name(player_data),
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
        matches_docs: list[DocumentSnapshot] | list[Match],
    ) -> tuple[set[Any], set[Any]]:
        """Collect all unique user and team references from match documents."""
        player_refs = set()
        team_refs = set()
        for match_doc in matches_docs:
            if hasattr(match_doc, "to_dict"):
                match = cast("DocumentSnapshot", match_doc).to_dict()
            else:
                match = cast("dict[str, Any]", match_doc)

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
        db: Client, matches_docs: list[DocumentSnapshot] | list[Match]
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
        profile_user_data: User | dict[str, Any],
    ) -> list[Match]:
        """Format matches for the public profile view with consistent alignment."""
        matches_docs = [item["doc"] for item in display_items]
        users_map, _ = UserService._fetch_match_entities(db, matches_docs)
        profile_username = profile_user_data.get("username", "Unknown")
        final_matches: list[Match] = []

        for item in display_items:
            data = item["data"]
            alignment = UserService._get_profile_match_alignment(
                data, user_id, profile_username, users_map
            )

            final_matches.append(
                cast(
                    "Match",
                    {
                        "id": item["doc"].id,
                        "match_date": data.get("matchDate"),
                        "player1_score": data.get("player1Score", 0),
                        "player2_score": data.get("player2Score", 0),
                        **alignment,
                    },
                )
            )
        return final_matches

    @staticmethod
    def get_public_groups(db: Client, limit: int = 10) -> list[Group]:
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
            g_data = doc.to_dict()
            if g_data and (ref := g_data.get("ownerRef")):
                owner_refs.append(ref)
        unique_owner_refs = list({ref for ref in owner_refs if ref})

        owners_data = {}
        if unique_owner_refs:
            owner_docs = db.get_all(unique_owner_refs)
            owners_data = {doc.id: doc.to_dict() for doc in owner_docs if doc.exists}

        guest_user = {"username": "Guest", "id": "unknown"}

        enriched_groups: list[Group] = []
        for doc in public_group_docs:
            data = cast("Group", doc.to_dict())
            if data is None:
                continue
            data["id"] = doc.id
            owner_ref = data.get("ownerRef")
            o_id = str(getattr(owner_ref, "id", ""))
            if owner_ref and o_id in owners_data:
                data["owner"] = cast("User", owners_data[o_id])
            else:
                data["owner"] = guest_user
            enriched_groups.append(data)

        return enriched_groups

    @staticmethod
    def format_matches_for_dashboard(
        db: Client, matches_docs: list[DocumentSnapshot] | list[Match], user_id: str
    ) -> list[Match]:
        """Enrich match documents with user and team data for dashboard display."""
        users_map, teams_map = UserService._fetch_match_entities(db, matches_docs)

        # Batch fetch tournament names
        tournament_ids = set()
        for m in matches_docs:
            if hasattr(m, "to_dict"):
                m_data = cast("DocumentSnapshot", m).to_dict()
            else:
                m_data = cast("dict[str, Any]", m)
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
            if hasattr(match_doc, "to_dict"):
                m_data = cast("DocumentSnapshot", match_doc).to_dict()
                m_id = cast("DocumentSnapshot", match_doc).id
            else:
                m_data = cast("dict[str, Any]", match_doc)
                m_id = m_data.get("id", "")

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
                cast(
                    "Match",
                    {
                        "id": m_id,
                        "player1": p1_info,
                        "player2": p2_info,
                        "player1_score": m_data.get("player1Score", 0),
                        "player2_score": m_data.get("player2Score", 0),
                        "winner": winner,
                        "date": m_data.get("matchDate", "N/A"),
                        "match_date": m_data.get("matchDate"),
                        "is_group_match": bool(m_data.get("groupId")),
                        "match_type": m_data.get("matchType", "singles"),
                        "user_result": user_result,
                        "team1_name": t1_name,
                        "team2_name": t2_name,
                        "tournament_name": tournament_name,
                    },
                )
            )
        return matches_data

    @staticmethod
    def _get_user_match_won_lost(
        match_data: dict[str, Any], user_id: str
    ) -> tuple[bool, bool]:
        """Determine if the user won or lost the match, including handling of draws."""
        match_type = match_data.get("matchType", "singles")
        p1_score = match_data.get("player1Score", 0)
        p2_score = match_data.get("player2Score", 0)

        user_won = False
        user_lost = False

        if match_type == "doubles":
            team1_refs = match_data.get("team1", [])
            in_team1 = any(ref.id == user_id for ref in team1_refs)
            if in_team1:
                user_won, user_lost = (p1_score > p2_score), (p1_score <= p2_score)
            else:
                user_won, user_lost = (p2_score > p1_score), (p2_score <= p1_score)
        else:
            p1_ref = match_data.get("player1Ref")
            is_player1 = p1_ref and p1_ref.id == user_id
            if is_player1:
                user_won, user_lost = (p1_score > p2_score), (p1_score <= p2_score)
            else:
                user_won, user_lost = (p2_score > p1_score), (p2_score <= p1_score)

        return user_won, user_lost

    @staticmethod
    def _calculate_streak(processed: list[dict[str, Any]]) -> tuple[int, str]:
        """Calculate current streak from processed matches."""
        if not processed:
            return 0, "N/A"

        last_won = processed[0]["user_won"]
        streak_type = "W" if last_won else "L"
        current_streak = 0
        for m in processed:
            if m["user_won"] == last_won:
                current_streak += 1
            else:
                break
        return current_streak, streak_type

    @staticmethod
    def calculate_stats(
        matches: list[DocumentSnapshot] | list[Match], user_id: str
    ) -> UserStats:
        """Calculate aggregate performance statistics from a list of matches."""
        wins = losses = 0
        processed = []

        for match_doc in matches:
            if hasattr(match_doc, "to_dict"):
                match_data = cast("DocumentSnapshot", match_doc).to_dict()
                create_time = cast("DocumentSnapshot", match_doc).create_time
            else:
                match_data = cast("dict[str, Any]", match_doc)
                create_time = None

            if not match_data:
                continue

            won, lost = UserService._get_user_match_won_lost(match_data, user_id)
            if won:
                wins += 1
            elif lost:
                losses += 1

            processed.append(
                {
                    "doc": match_doc,
                    "data": match_data,
                    "date": match_data.get("matchDate") or create_time,
                    "user_won": won,
                }
            )

        total = wins + losses
        win_rate = (wins / total) * 100 if total > 0 else 0
        processed.sort(key=lambda x: x["date"] or datetime.datetime.min, reverse=True)

        streak, s_type = UserService._calculate_streak(processed)

        return cast(
            "UserStats",
            {
                "wins": wins,
                "losses": losses,
                "total_games": total,
                "win_rate": win_rate,
                "current_streak": streak,
                "streak_type": s_type,
                "processed_matches": processed,
            },
        )

    @staticmethod
    def _process_h2h_match(
        data: dict[str, Any], user_id_1: str, user_id_2: str
    ) -> tuple[int, int, int]:
        """Process a single match for H2H stats and return (wins, losses, points)."""
        wins = losses = points = 0
        match_type = data.get("matchType", "singles")

        if match_type == "singles":
            is_p1 = data.get("player1Id") == user_id_1
            winner_id = data.get("winnerId")
            if winner_id == user_id_1:
                wins += 1
            elif winner_id == user_id_2:
                losses += 1

            p1_score = data.get("player1Score", 0)
            p2_score = data.get("player2Score", 0)
            points += (p1_score - p2_score) if is_p1 else (p2_score - p1_score)
        else:
            team1_ids = data.get("team1Id", [])
            team2_ids = data.get("team2Id", [])
            winner_id = data.get("winnerId")

            if user_id_1 in team1_ids and user_id_2 in team2_ids:
                if winner_id == "team1":
                    wins += 1
                else:
                    losses += 1
                points += data.get("player1Score", 0) - data.get("player2Score", 0)
            elif user_id_1 in team2_ids and user_id_2 in team1_ids:
                if winner_id == "team2":
                    wins += 1
                else:
                    losses += 1
                points += data.get("player2Score", 0) - data.get("player1Score", 0)

        return wins, losses, points

    @staticmethod
    def get_h2h_stats(
        db: Client, user_id_1: str, user_id_2: str
    ) -> dict[str, Any] | None:
        """Fetch head-to-head statistics between two users."""
        wins = losses = points = 0

        # Build queries
        matches_ref = db.collection("matches")

        q1 = (
            matches_ref.where(
                filter=firestore.FieldFilter("player1Id", "==", user_id_1)
            )
            .where(filter=firestore.FieldFilter("player2Id", "==", user_id_2))
            .where(filter=firestore.FieldFilter("status", "==", "completed"))
        )
        q2 = (
            matches_ref.where(
                filter=firestore.FieldFilter("player1Id", "==", user_id_2)
            )
            .where(filter=firestore.FieldFilter("player2Id", "==", user_id_1))
            .where(filter=firestore.FieldFilter("status", "==", "completed"))
        )
        q3 = (
            matches_ref.where(
                filter=firestore.FieldFilter(
                    "participants", "array_contains", user_id_1
                )
            )
            .where(filter=firestore.FieldFilter("matchType", "==", "doubles"))
            .where(filter=firestore.FieldFilter("status", "==", "completed"))
        )

        for q_obj in [q1, q2, q3]:
            for match in q_obj.stream():
                data = match.to_dict()
                if data:
                    w, l_count, p_diff = UserService._process_h2h_match(
                        data, user_id_1, user_id_2
                    )
                    wins += w
                    losses += l_count
                    points += p_diff

        if wins > 0 or losses > 0:
            return {"wins": wins, "losses": losses, "point_diff": points}
        return None

    @staticmethod
    def accept_friend_request(db: Client, user_id: str, requester_id: str) -> bool:
        """Accept a friend request and ensure reciprocal status."""
        try:
            batch = db.batch()

            # Update status in current user's friend list
            my_friend_ref = (
                db.collection("users")
                .document(user_id)
                .collection("friends")
                .document(requester_id)
            )
            batch.update(my_friend_ref, {"status": "accepted"})

            # Update status in the other user's friend list
            their_friend_ref = (
                db.collection("users")
                .document(requester_id)
                .collection("friends")
                .document(user_id)
            )
            batch.update(their_friend_ref, {"status": "accepted"})

            batch.commit()
            return True
        except Exception as e:
            current_app.logger.error(f"Error accepting friend request: {e}")
            return False

    @staticmethod
    def cancel_friend_request(db: Client, user_id: str, target_user_id: str) -> bool:
        """Cancel or decline a friend request for both users."""
        try:
            batch = db.batch()

            # Delete request from current user's list
            my_friend_ref = (
                db.collection("users")
                .document(user_id)
                .collection("friends")
                .document(target_user_id)
            )
            batch.delete(my_friend_ref)

            # Delete request from the other user's list
            their_friend_ref = (
                db.collection("users")
                .document(target_user_id)
                .collection("friends")
                .document(user_id)
            )
            batch.delete(their_friend_ref)

            batch.commit()
            return True
        except Exception as e:
            current_app.logger.error(f"Error cancelling friend request: {e}")
            return False

    @staticmethod
    def get_group_rankings(db: Client, user_id: str) -> list[UserRanking]:
        """Fetch group rankings for a user."""
        from pickaladder.group.utils import (  # noqa: PLC0415
            get_group_leaderboard,
        )

        user_ref = db.collection("users").document(user_id)
        group_rankings: list[UserRanking] = []
        my_groups_query = (
            db.collection("groups")
            .where(filter=firestore.FieldFilter("members", "array_contains", user_ref))
            .stream()
        )
        for group_doc in my_groups_query:
            group_data = group_doc.to_dict()
            if group_data is None:
                continue
            leaderboard = get_group_leaderboard(group_doc.id)
            user_ranking_data = None
            for i, player in enumerate(leaderboard):
                if player["id"] == user_id:
                    rank = i + 1
                    user_ranking_data = {
                        "group_id": group_doc.id,
                        "group_name": group_data.get("name", "N/A"),
                        "rank": rank,
                        "points": player.get("avg_score", 0),
                        "form": player.get("form", []),
                    }
                    if i > 0:
                        player_above = leaderboard[i - 1]
                        user_ranking_data["player_above"] = player_above.get("name")
                        user_ranking_data["points_to_overtake"] = player_above.get(
                            "avg_score", 0
                        ) - player.get("avg_score", 0)
                    break

            if user_ranking_data:
                group_rankings.append(cast("UserRanking", user_ranking_data))
            else:
                group_rankings.append(
                    cast(
                        "UserRanking",
                        {
                            "group_id": group_doc.id,
                            "group_name": group_data.get("name", "N/A"),
                            "rank": "N/A",
                            "points": 0,
                            "form": [],
                        },
                    )
                )
        return group_rankings
