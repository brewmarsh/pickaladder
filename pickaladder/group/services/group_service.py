"""Service layer for group operations and data orchestration."""

from __future__ import annotations

import secrets
from typing import Any

from firebase_admin import firestore
from flask import current_app, url_for

from pickaladder.group.utils import (
    get_group_leaderboard,
    get_random_joke,
    send_invite_email_background,
)
from pickaladder.group.utils import (
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
            {ref.path: ref for ref in refs if hasattr(ref, "path")}.values()
        )
        if not unique_refs:
            return {}

        docs = db.get_all(unique_refs)
        return {doc.id: {**doc.to_dict(), "id": doc.id} for doc in docs if doc.exists}

    @staticmethod
    def _enrich_single_match(
        match_doc: Any, teams_map: dict[str, Any], players_map: dict[str, Any]
    ) -> dict[str, Any]:
        """Attach team and player data to a single match dictionary."""
        match_data = match_doc.to_dict()
        match_data["id"] = match_doc.id

        # Attach Teams
        for field in ["team1", "team2"]:
            if (ref := match_data.get(f"{field}Ref")) and isinstance(
                ref, firestore.DocumentReference
            ):
                match_data[field] = teams_map.get(ref.id)

        # Attach Players
        player_keys = [
            "player1",
            "player2",
            "partner",
            "opponent1",
            "opponent2",
            "player1Ref",
            "player2Ref",
            "partnerRef",
            "opponent1Ref",
            "opponent2Ref",
        ]
        for key in player_keys:
            ref = match_data.get(key)
            if isinstance(ref, firestore.DocumentReference):
                target = key.replace("Ref", "")
                match_data[target] = players_map.get(ref.id, GUEST_USER)

        return match_data

    @staticmethod
    def _calculate_giant_slayer_upsets(recent_matches: list[dict[str, Any]]) -> None:
        """Identify 'giant slayer' upsets based on DUPR rating gaps."""
        for match_data in recent_matches:
            winner_player = None
            loser_player = None
            if match_data.get("winner") == "team1":
                winner_player = match_data.get("player1")
                loser_player = match_data.get("player2")
            elif match_data.get("winner") == "team2":
                winner_player = match_data.get("player2")
                loser_player = match_data.get("player1")

            if winner_player and loser_player:
                winner_rating = float(winner_player.get("dupr_rating") or 0.0)
                loser_rating = float(loser_player.get("dupr_rating") or 0.0)
                if loser_rating > 0 and winner_rating > 0:
                    if (loser_rating - winner_rating) >= UPSET_THRESHOLD:
                        match_data["is_upset"] = True

    @staticmethod
    def _fetch_group_teams(
        db: Any, group_id: str, member_ids: set[str], recent_matches_docs: list[Any]
    ) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        """Calculate team leaderboard and best buds for a group."""
        team_stats = GroupService._calculate_team_stats(recent_matches_docs)
        if not team_stats:
            return [], None

        team_ids = list(team_stats.keys())
        team_refs = [db.collection("teams").document(tid) for tid in team_ids]
        team_docs = db.get_all(team_refs)

        all_member_refs = []
        enriched_team_docs = []
        for doc in team_docs:
            if doc.exists:
                team_data = {**doc.to_dict(), "id": doc.id}
                all_member_refs.extend(team_data.get("members", []))
                enriched_team_docs.append(team_data)

        members_map = GroupService._batch_fetch_entities(db, all_member_refs)

        team_leaderboard = []
        for team_data in enriched_team_docs:
            stats = team_stats[team_data["id"]]
            stats["win_percentage"] = (
                (stats["wins"] / stats["games"]) * 100 if stats["games"] > 0 else 0
            )

            team_data["member_details"] = [
                members_map[m.id]
                for m in team_data.get("members", [])
                if m.id in members_map
            ]
            team_leaderboard.append({"team": team_data, "stats": stats})

        team_leaderboard.sort(key=lambda x: x["stats"]["wins"], reverse=True)
        best_buds = GroupService._extract_best_buds(team_leaderboard)

        return team_leaderboard, best_buds

    @staticmethod
    def _calculate_team_stats(recent_matches_docs: list[Any]) -> dict[str, Any]:
        """Aggregate wins/losses per team from match history."""
        stats = {}
        for doc in recent_matches_docs:
            data = doc.to_dict()
            if data.get("matchType") != "doubles":
                continue

            t1_id = data.get("team1Ref").id if data.get("team1Ref") else None
            t2_id = data.get("team2Ref").id if data.get("team2Ref") else None
            if not t1_id or not t2_id:
                continue

            for tid in [t1_id, t2_id]:
                if tid not in stats:
                    stats[tid] = {"wins": 0, "losses": 0, "games": 0}

            p1_score = data.get("player1Score", data.get("team1Score", 0))
            p2_score = data.get("player2Score", data.get("team2Score", 0))

            stats[t1_id]["games"] += 1
            stats[t2_id]["games"] += 1

            if p1_score > p2_score:
                stats[t1_id]["wins"] += 1
                stats[t2_id]["losses"] += 1
            elif p2_score > p1_score:
                stats[t2_id]["wins"] += 1
                stats[t1_id]["losses"] += 1
        return stats

    @staticmethod
    def _extract_best_buds(
        team_leaderboard: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Identify the top-performing team for the 'Best Buds' feature."""
        if not team_leaderboard:
            return None
        top_team = team_leaderboard[0]
        if top_team["stats"]["wins"] > 0:
            best_buds = top_team["team"].copy()
            best_buds["stats"] = top_team["stats"]
            return best_buds
        return None

    @staticmethod
    def _get_pending_invites(db: Any, group_id: str) -> list[dict[str, Any]]:
        """Fetch pending invites for a group."""
        pending_members = []
        invites_ref = db.collection("group_invites")
        query = invites_ref.where(
            filter=firestore.FieldFilter("group_id", "==", group_id)
        ).where(filter=firestore.FieldFilter("used", "==", False))

        pending_invites_docs = list(query.stream())
        for doc in pending_invites_docs:
            data = doc.to_dict()
            data["token"] = doc.id
            pending_members.append(data)

        invite_emails = [
            invite.get("email") for invite in pending_members if invite.get("email")
        ]
        if invite_emails:
            user_docs = {}
            for i in range(0, len(invite_emails), 30):
                chunk = invite_emails[i : i + 30]
                users_ref = db.collection("users")
                user_query = users_ref.where(
                    filter=firestore.FieldFilter("email", "in", chunk)
                )
                for doc in user_query.stream():
                    user_docs[doc.to_dict()["email"]] = doc.to_dict()

            for invite in pending_members:
                user_data = user_docs.get(invite.get("email"))
                if user_data:
                    invite["username"] = user_data.get("username", invite.get("name"))
                    invite["profilePictureUrl"] = user_data.get("profilePictureUrl")

        pending_members.sort(key=lambda x: x.get("created_at") or 0, reverse=True)
        return pending_members

    @staticmethod
    def invite_friend(db: Any, group_id: str, friend_id: str) -> None:
        """Add a friend to a group."""
        group_ref = db.collection("groups").document(group_id)
        friend_ref = db.collection("users").document(friend_id)
        group_ref.update({"members": firestore.ArrayUnion([friend_ref])})

    @staticmethod
    def invite_by_email(  # noqa: PLR0913
        db: Any,
        group_id: str,
        group_name: str,
        email: str,
        name: str,
        current_user_id: str,
    ) -> None:
        """Create a group invitation and send an email."""
        original_email = email
        email = original_email.lower()

        users_ref = db.collection("users")
        existing_user = None

        query_lower = users_ref.where(
            filter=firestore.FieldFilter("email", "==", email)
        ).limit(1)
        docs = list(query_lower.stream())

        if docs:
            existing_user = docs[0]
        elif original_email != email:
            query_orig = users_ref.where(
                filter=firestore.FieldFilter("email", "==", original_email)
            ).limit(1)
            docs = list(query_orig.stream())
            if docs:
                existing_user = docs[0]

        if existing_user:
            invite_email = existing_user.to_dict().get("email")
        else:
            invite_email = email
            ghost_user_data = {
                "email": email,
                "name": name,
                "is_ghost": True,
                "createdAt": firestore.SERVER_TIMESTAMP,
                "username": f"ghost_{secrets.token_hex(4)}",
            }
            db.collection("users").add(ghost_user_data)

        token = secrets.token_urlsafe(32)
        invite_data = {
            "group_id": group_id,
            "email": invite_email,
            "name": name,
            "inviter_id": current_user_id,
            "created_at": firestore.SERVER_TIMESTAMP,
            "used": False,
            "status": "sending",
        }
        db.collection("group_invites").document(token).set(invite_data)

        invite_url = url_for("group.handle_invite", token=token, _external=True)
        email_data = {
            "to": email,
            "subject": f"Join {group_name} on pickaladder!",
            "template": "email/group_invite.html",
            "name": name,
            "group_name": group_name,
            "invite_url": invite_url,
            "joke": get_random_joke(),
        }

        send_invite_email_background(
            current_app._get_current_object(),  # type: ignore[attr-defined]
            token,
            email_data,
        )
