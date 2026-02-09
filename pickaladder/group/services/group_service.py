"""Service layer for group operations and data orchestration."""

from __future__ import annotations

import secrets
from typing import Any

from firebase_admin import firestore, storage
from flask import current_app, url_for
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from pickaladder.group.services.leaderboard import get_group_leaderboard
from pickaladder.group.services.match_parser import (
    _get_match_scores,
    _resolve_team_document_ids,
)
from pickaladder.group.services.stats import (
    get_head_to_head_stats as get_h2h_stats,
)

UPSET_THRESHOLD = 0.25
GUEST_USER = {"username": "Guest", "id": "unknown"}


class GroupNotFound(Exception):
    """Exception raised when a group is not found."""

    pass


class AccessDenied(Exception):
    """Exception raised when a user does not have permission to access a group."""

    pass


class GroupService:
    """Service class for group-related operations."""

    @staticmethod
    def get_user_groups(db: Any, user_id: str) -> list[dict[str, Any]]:
        """Fetch and enrich all groups the user belongs to."""
        user_ref = db.collection("users").document(user_id)
        my_groups_query = db.collection("groups").where(
            filter=firestore.FieldFilter("members", "array_contains", user_ref)
        )
        my_group_docs = list(my_groups_query.stream())

        # Enrich groups with owner data
        owner_refs = [
            group.to_dict().get("ownerRef")
            for group in my_group_docs
            if group.to_dict().get("ownerRef")
        ]
        unique_owner_refs = list({ref for ref in owner_refs if ref})

        owners_data = {}
        if unique_owner_refs:
            owner_docs = db.get_all(unique_owner_refs)
            owners_data = {doc.id: doc.to_dict() for doc in owner_docs if doc.exists}

        def enrich_group(group_doc: Any) -> dict[str, Any]:
            group_data: dict[str, Any] = group_doc.to_dict()
            group_id = group_doc.id
            group_data["id"] = group_id
            group_data["member_count"] = len(group_data.get("members", []))

            # Current User's Stats for this group
            leaderboard = get_group_leaderboard(group_id)
            user_entry = next((p for p in leaderboard if p["id"] == user_id), None)

            if user_entry:
                group_data["user_rank"] = leaderboard.index(user_entry) + 1
                group_data["user_record"] = (
                    f"{user_entry.get('wins', 0)}W - {user_entry.get('losses', 0)}L"
                )
            else:
                group_data["user_rank"] = "N/A"
                group_data["user_record"] = "0W - 0L"

            owner_ref = group_data.get("ownerRef")
            if owner_ref and owner_ref.id in owners_data:
                group_data["owner"] = owners_data[owner_ref.id]
            else:
                group_data["owner"] = GUEST_USER
            return group_data

        return [{"group": enrich_group(doc)} for doc in my_group_docs]

    @staticmethod
    def create_group(
        db: Any,
        user_id: str,
        form_data: dict[str, Any],
        profile_picture: FileStorage | None = None,
    ) -> str:
        """Create a new group and return its ID."""
        user_ref = db.collection("users").document(user_id)
        group_data = {
            "name": form_data.get("name"),
            "description": form_data.get("description"),
            "location": form_data.get("location"),
            "is_public": form_data.get("is_public", False),
            "ownerRef": user_ref,
            "members": [user_ref],
            "createdAt": firestore.SERVER_TIMESTAMP,
        }
        _, new_group_ref = db.collection("groups").add(group_data)
        group_id = new_group_ref.id

        if profile_picture:
            url = GroupService.upload_group_profile_picture(group_id, profile_picture)
            if url:
                new_group_ref.update({"profilePictureUrl": url})

        return group_id

    @staticmethod
    def update_group(
        db: Any,
        group_id: str,
        user_id: str,
        form_data: dict[str, Any],
        profile_picture: FileStorage | None = None,
    ) -> None:
        """Update an existing group's details."""
        group_ref = db.collection("groups").document(group_id)
        group = group_ref.get()
        if not group.exists:
            raise GroupNotFound("Group not found")

        group_data = group.to_dict()
        owner_ref = group_data.get("ownerRef")
        if not owner_ref or owner_ref.id != user_id:
            raise AccessDenied("You do not have permission to edit this group")

        update_data = {
            "name": form_data.get("name"),
            "description": form_data.get("description"),
            "location": form_data.get("location"),
            "is_public": form_data.get("is_public", False),
        }

        if profile_picture:
            url = GroupService.upload_group_profile_picture(group_id, profile_picture)
            if url:
                update_data["profilePictureUrl"] = url

        group_ref.update(update_data)

    @staticmethod
    def upload_group_profile_picture(group_id: str, file: FileStorage) -> str | None:
        """Upload a group profile picture and return its public URL."""
        try:
            filename = secure_filename(file.filename or "group_profile.jpg")
            bucket = storage.bucket()
            blob = bucket.blob(f"group_pictures/{group_id}/{filename}")
            blob.upload_from_file(file)
            blob.make_public()
            return blob.public_url
        except Exception as e:
            current_app.logger.error(f"Error uploading group image: {e}")
            return None

    @staticmethod
    def get_group_details(
        db: Any,
        group_id: str,
        user_id: str,
        player_a_id: str | None = None,
        player_b_id: str | None = None,
    ) -> dict[str, Any]:
        """Fetch all details for a group view."""
        group_ref = db.collection("groups").document(group_id)
        group = group_ref.get()
        if not group.exists:
            raise GroupNotFound("Group not found.")

        group_data = group.to_dict()
        group_data["id"] = group.id
        user_ref = db.collection("users").document(user_id)

        # Pre-calculate rivalry stats if players are selected
        rivalry_stats = None
        if player_a_id and player_b_id:
            rivalry_stats = get_h2h_stats(group_id, player_a_id, player_b_id)

        # Fetch members' data
        member_refs = group_data.get("members", [])
        member_ids = {ref.id for ref in member_refs}
        members_snapshots = [ref.get() for ref in member_refs]
        members = []
        for snapshot in members_snapshots:
            if snapshot.exists:
                data = snapshot.to_dict()
                data["id"] = snapshot.id
                members.append(data)

        # Fetch owner's data
        owner = None
        owner_ref = group_data.get("ownerRef")
        if owner_ref:
            owner_doc = owner_ref.get()
            if owner_doc.exists:
                owner = owner_doc.to_dict()

        is_member = user_id in member_ids

        # Get eligible friends for invitation
        eligible_friends = GroupService._get_eligible_friends(db, user_ref, member_ids)

        # Fetch leaderboard and matches
        leaderboard = get_group_leaderboard(group_id)
        recent_matches_docs, recent_matches = GroupService._fetch_recent_matches(
            db, group_id
        )
        team_leaderboard, best_buds = GroupService._fetch_group_teams(
            db, group_id, member_ids, recent_matches_docs
        )

        # Fetch Pending Invites
        pending_members = []
        if is_member:
            pending_members = GroupService._get_pending_invites(db, group_id)

        return {
            "group": group_data,
            "group_id": group.id,
            "members": members,
            "owner": owner,
            "current_user_id": user_id,
            "leaderboard": leaderboard,
            "pending_members": pending_members,
            "is_member": is_member,
            "recent_matches": recent_matches,
            "best_buds": best_buds,
            "team_leaderboard": team_leaderboard,
            "rivalry_stats": rivalry_stats,
            "playerA_id": player_a_id,
            "playerB_id": player_b_id,
            "eligible_friends": eligible_friends,
        }

    @staticmethod
    def _get_eligible_friends(
        db: Any, user_ref: Any, member_ids: set[str]
    ) -> list[Any]:
        """Fetch friends of the user who are not already in the group."""
        friends_query = (
            user_ref.collection("friends")
            .where(filter=firestore.FieldFilter("status", "==", "accepted"))
            .stream()
        )
        friend_ids = {doc.id for doc in friends_query}
        eligible_friend_ids = list(friend_ids - member_ids)

        eligible_friends = []
        if eligible_friend_ids:
            friend_refs = [
                db.collection("users").document(uid) for uid in eligible_friend_ids
            ]
            friend_docs = db.get_all(friend_refs)
            eligible_friends = [doc for doc in friend_docs if doc.exists]
        return eligible_friends

    @staticmethod
    def _fetch_recent_matches(
        db: Any, group_id: str
    ) -> tuple[list[Any], list[dict[str, Any]]]:
        """Fetch and enrich recent matches for a group."""
        matches_ref = db.collection("matches")
        matches_query = (
            matches_ref.where(filter=firestore.FieldFilter("groupId", "==", group_id))
            .order_by("matchDate", direction=firestore.Query.DESCENDING)
            .limit(20)
        )
        recent_matches_docs = list(matches_query.stream())

        # Collect and fetch associated entities
        team_refs, player_refs = GroupService._collect_refs_from_matches(
            recent_matches_docs
        )
        teams_map = GroupService._batch_fetch_entities(db, team_refs)
        players_map = GroupService._batch_fetch_entities(db, player_refs)

        # Enrich match data
        recent_matches = []
        for match_doc in recent_matches_docs:
            match_data = GroupService._enrich_single_match(
                match_doc, teams_map, players_map
            )
            recent_matches.append(match_data)

        GroupService._calculate_giant_slayer_upsets(recent_matches)

        return recent_matches_docs, recent_matches

    @staticmethod
    def _collect_refs_from_matches(
        matches_docs: list[Any],
    ) -> tuple[list[Any], list[Any]]:
        """Extract team and player references from match documents."""
        team_refs = []
        player_refs = []
        player_keys = [
            "player1Ref",
            "player2Ref",
            "partnerRef",
            "opponent1Ref",
            "opponent2Ref",
            "player1",
            "player2",
            "partner",
            "opponent1",
            "opponent2",
        ]

        for doc in matches_docs:
            data = doc.to_dict()
            for field in ["team1Ref", "team2Ref"]:
                if (ref := data.get(field)) and isinstance(
                    ref, firestore.DocumentReference
                ):
                    team_refs.append(ref)

            for key in player_keys:
                if (ref := data.get(key)) and isinstance(
                    ref, firestore.DocumentReference
                ):
                    player_refs.append(ref)

        return team_refs, player_refs

    @staticmethod
    def _batch_fetch_entities(db: Any, refs: list[Any]) -> dict[str, Any]:
        """Batch fetch multiple Firestore documents and return a map by ID."""
        if not refs:
            return {}

        unique_refs = list(
            {ref.path: ref for ref in refs