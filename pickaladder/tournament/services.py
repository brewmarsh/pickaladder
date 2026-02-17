"""Service layer for tournament business logic."""

from __future__ import annotations

import logging
import datetime
from typing import TYPE_CHECKING, Any, cast

from firebase_admin import firestore

from pickaladder.teams.services import TeamService
from pickaladder.user.helpers import smart_display_name
from pickaladder.utils import send_email

from .utils import get_tournament_standings

MIN_PARTICIPANTS_FOR_GENERATION = 2

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client
    from google.cloud.firestore_v1.document import DocumentReference
    from google.cloud.firestore_v1.transaction import Transaction


class TournamentGenerator:
    """Helper to generate tournament brackets and pairings."""

    @staticmethod
    def generate_round_robin(participant_ids: list[str]) -> list[dict[str, Any]]:
        """Generate round robin pairings using the circle method."""
        if len(participant_ids) < MIN_PARTICIPANTS_FOR_GENERATION:
            return []

        # Handle odd number of participants by adding a BYE
        ids = list(participant_ids)
        if len(ids) % 2 != 0:
            ids.append(None)  # type: ignore

        n = len(ids)
        pairings = []
        db = firestore.client()

        # Circle Method implementation
        for _ in range(n - 1):
            for i in range(n // 2):
                p1 = ids[i]
                p2 = ids[n - 1 - i]
                if p1 is not None and p2 is not None:
                    pairings.append(
                        {
                            "player1Ref": db.collection("users").document(p1),
                            "player2Ref": db.collection("users").document(p2),
                            "matchType": "singles",
                            "status": "DRAFT",
                            "createdAt": firestore.SERVER_TIMESTAMP,
                            "participants": [p1, p2],
                        }
                    )
            # Rotate: keep the first element fixed, rotate others
            ids = [ids[0]] + [ids[-1]] + ids[1:-1]

        return pairings


class TournamentService:
    """Handles business logic and data access for tournaments."""

    @staticmethod
    def _get_participant_refs(
        db: Client, participant_objs: list[dict[str, Any]]
    ) -> list[DocumentReference]:
        """Extract user references from participant objects."""
        user_refs = []
        for obj in participant_objs:
            if not obj:
                continue
            if obj.get("userRef"):
                user_refs.append(obj["userRef"])
            elif obj.get("user_id"):
                user_refs.append(db.collection("users").document(obj["user_id"]))
        return user_refs

    @staticmethod
    def _resolve_participants(
        db: Client, participant_objs: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Internal helper to resolve participant user data."""
        if not participant_objs:
            return []

        user_refs = TournamentService._get_participant_refs(db, participant_objs)
        if not user_refs:
            return []

        user_docs = cast(list[Any], db.get_all(user_refs))
        users_map = {
            doc.id: {**(doc.to_dict() or {}), "id": doc.id}
            for doc in user_docs
            if doc.exists
        }

        participants = []
        for obj in participant_objs:
            if not obj:
                continue
            user_ref = obj.get("userRef")
            uid = user_ref.id if user_ref else obj.get("user_id")
            if uid and uid in users_map:
                u_data = users_map[uid]
                participants.append(
                    {
                        "user": u_data,
                        "status": obj.get("status", "pending"),
                        "display_name": smart_display_name(u_data),
                        "team_name": obj.get("team_name"),
                    }
                )
        return participants

    @staticmethod
    def _get_invitable_players(
        db: Client, user_uid: str, current_participant_ids: set[str]
    ) -> list[dict[str, Any]]:
        """Internal helper to find invite candidates."""
        user_ref = db.collection("users").document(user_uid)

        # Friends
        friends_query = user_ref.collection("friends").stream()
        friend_ids = {doc.id for doc in friends_query}

        # Groups
        groups_query = (
            db.collection("groups")
            .where(filter=firestore.FieldFilter("members", "array_contains", user_ref))
            .stream()
        )
        group_member_ids = set()
        for group_doc in groups_query:
            g_data = group_doc.to_dict()
            if g_data and "members" in g_data:
                for m_ref in g_data["members"]:
                    group_member_ids.add(m_ref.id)

        all_ids = {str(uid) for uid in (friend_ids | group_member_ids)}
        all_ids.discard(str(user_uid))
        final_ids = all_ids - current_participant_ids

        invitable_users = []
        if final_ids:
            u_refs = [db.collection("users").document(uid) for uid in final_ids]
            u_docs = cast(list[Any], db.get_all(u_refs))
            for u_doc in u_docs:
                if u_doc.exists:
                    u_data = u_doc.to_dict()
                    if u_data:
                        u_data["id"] = u_doc.id
                        invitable_users.append(u_data)

        invitable_users.sort(key=lambda u: smart_display_name(u).lower())
        return invitable_users

    @staticmethod
    def list_tournaments(
        user_uid: str, db: Client | None = None
    ) -> list[dict[str, Any]]:
        """Fetch all tournaments for a user."""
        if db is None:
            db = firestore.client()
        user_ref = db.collection("users").document(user_uid)

        owned = list(db.collection("tournaments").where(filter=firestore.FieldFilter("ownerRef", "==", user_ref)).stream())
        participating = list(db.collection("tournaments").where(filter=firestore.FieldFilter("participant_ids", "array_contains", user_uid)).stream())

        results = {}
        for doc in owned + participating:
            if doc.id not in results:
                data = doc.to_dict()
                if data:
                    data["id"] = doc.id
                    raw_date = data.get("start_date") or data.get("date")
                    if raw_date and hasattr(raw_date, "to_datetime"):
                        data["date_display"] = raw_date.to_datetime().strftime("%b %d, %Y")
                    results[doc.id] = data

        return list(results.values())

    @staticmethod
    def create_tournament(
        data: dict[str, Any], user_uid: str, db: Client | None = None
    ) -> str:
        """Create a tournament and return its ID."""
        if db is None:
            db = firestore.client()
        user_ref = db.collection("users").document(user_uid)

        tournament_payload = {
            "name": data["name"],
            "date": data.get("start_date") or data.get("date"),
            "location": data["location"],
            "matchType": data.get("match_type") or data.get("mode", "SINGLES").lower(),
            "mode": data.get("mode", "SINGLES"),
            "ownerRef": user_ref,
            "organizer_id": user_uid,
            "status": "Active",
            "participants": [{"userRef": user_ref, "status": "accepted"}],
            "participant_ids": [user_uid],
            "createdAt": firestore.SERVER_TIMESTAMP,
        }
        _, ref = db.collection("tournaments").add(tournament_payload)
        return str(ref.id)

    @staticmethod
    def get_tournament_details(
        tournament_id: str, user_uid: str, db: Client | None = None
    ) -> dict[str, Any] | None:
        """Fetch comprehensive details for the tournament view."""
        if db is None:
            db = firestore.client()
        doc = cast(Any, db.collection("tournaments").document(tournament_id).get())
        if not doc or not doc.exists:
            return None

        data = cast(dict[str, Any], doc.to_dict())
        data["id"] = doc.id

        raw_date = data.get("date")
        if raw_date and hasattr(raw_date, "to_datetime"):
            data["date_display"] = raw_date.to_datetime().strftime("%b %d, %Y")

        participants = TournamentService._resolve_participants(db, data.get("participants", []))
        standings = get_tournament_standings(db, tournament_id, data.get("matchType", "singles"))
        podium = standings[:3] if data.get("status") == "Completed" else []

        from pickaladder.user.services import UserService
        user_groups = UserService.get_user_groups(db, user_uid)

        is_owner = (
            data.get("organizer_id") == user_uid
            or (data.get("ownerRef") and data["ownerRef"].id == user_uid)
        )

        return {
            "tournament": data,
            "participants": participants,
            "standings": standings,
            "podium": podium,
            "user_groups": user_groups,
            "is_owner": is_owner,
        }

    @staticmethod
    def complete_tournament(
        tournament_id: str, user_uid: str, db: Client | None = None
    ) -> None:
        """Finalize tournament and send emails."""
        if db is None:
            db = firestore.client()
        ref = db.collection("tournaments").document(tournament_id)
        doc = cast(Any, ref.get())
        data = cast(dict[str, Any], doc.to_dict())

        if data.get("organizer_id") != user_uid and data["ownerRef"].id != user_uid:
            raise PermissionError("Only the organizer can complete the tournament.")

        ref.update({"status": "Completed"})

        standings = get_tournament_standings(db, tournament_id, data.get("matchType", "singles"))
        winner = standings[0]["name"] if standings else "No one"
        TournamentService._notify_participants(data, winner, standings)

    @staticmethod
    def _notify_participants(tournament_data: dict[str, Any], winner_name: str, standings: list[Any]) -> None:
        for p in tournament_data.get("participants", []):
            if p.get("status") == "accepted":
                u_doc = p["userRef"].get()
                if u_doc.exists:
                    u_data = u_doc.to_dict()
                    if u_data and u_data.get("email"):
                        send_email(
                            to=u_data["email"],
                            subject=f"Results: {tournament_data['name']}",
                            template="email/tournament_results.html",
                            user=u_data,
                            tournament=tournament_data,
                            winner_name=winner_name,
                            standings=standings[:3]
                        )