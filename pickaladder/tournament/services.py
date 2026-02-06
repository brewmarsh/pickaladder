"""Service layer for tournament business logic."""

from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING, Any, cast

from firebase_admin import firestore

from pickaladder.user.utils import UserService, smart_display_name
from pickaladder.utils import send_email

from .utils import get_tournament_standings

if TYPE_CHECKING:
    from google.cloud.firestore_v1.document import DocumentSnapshot

logger = logging.getLogger(__name__)


class TournamentService:
    """Handles business logic and data access for tournaments."""

    @staticmethod
    def list_tournaments(user_id: str, db: Any = None) -> list[dict[str, Any]]:
        """Fetch all tournaments associated with a user (owned or participating)."""
        if db is None:
            db = firestore.client()
        user_ref = db.collection("users").document(user_id)

        # Fetch tournaments where the user is an owner
        owned_tournaments = (
            db.collection("tournaments")
            .where(filter=firestore.FieldFilter("ownerRef", "==", user_ref))
            .stream()
        )

        # Fetch tournaments where user is a participant
        participating_tournaments = (
            db.collection("tournaments")
            .where(
                filter=firestore.FieldFilter(
                    "participant_ids", "array_contains", user_id
                )
            )
            .stream()
        )

        tournaments = []
        seen_ids = set()

        for doc in owned_tournaments:
            data = doc.to_dict()
            if data:
                data["id"] = doc.id
                tournaments.append(data)
                seen_ids.add(doc.id)

        for doc in participating_tournaments:
            if doc.id not in seen_ids:
                data = doc.to_dict()
                if data:
                    data["id"] = doc.id
                    tournaments.append(data)
                    seen_ids.add(doc.id)

        return tournaments

    @staticmethod
    def create_tournament(  # noqa: PLR0913
        user_id: str,
        name: str,
        date: datetime.date,
        location: str,
        match_type: str,
        db: Any = None,
    ) -> str:
        """Create a new tournament."""
        if db is None:
            db = firestore.client()
        user_ref = db.collection("users").document(user_id)
        tournament_data = {
            "name": name,
            "date": datetime.datetime.combine(date, datetime.time.min),
            "location": location,
            "matchType": match_type,
            "ownerRef": user_ref,
            "organizer_id": user_id,
            "status": "Active",
            "participants": [{"userRef": user_ref, "status": "accepted"}],
            "participant_ids": [user_id],
            "createdAt": firestore.SERVER_TIMESTAMP,
        }
        _, new_tournament_ref = db.collection("tournaments").add(tournament_data)
        return cast(str, new_tournament_ref.id)

    @staticmethod
    def get_tournament(tournament_id: str, db: Any = None) -> dict[str, Any] | None:
        """Fetch basic tournament data."""
        if db is None:
            db = firestore.client()
        tournament_ref = db.collection("tournaments").document(tournament_id)
        tournament_doc = cast("DocumentSnapshot", tournament_ref.get())

        if not tournament_doc.exists:
            return None

        data = tournament_doc.to_dict()
        if data:
            data["id"] = tournament_id
        return data

    @staticmethod
    def get_tournament_details(
        tournament_id: str, current_user_id: str, db: Any = None
    ) -> dict[str, Any] | None:
        """Resolve all data needed for the tournament view page."""
        if db is None:
            db = firestore.client()
        tournament_ref = db.collection("tournaments").document(tournament_id)
        tournament_doc = cast("DocumentSnapshot", tournament_ref.get())

        if not tournament_doc.exists:
            return None

        tournament_data = tournament_doc.to_dict()
        if tournament_data is None:
            return None

        tournament_data["id"] = tournament_doc.id

        # Format Date Display
        raw_date = tournament_data.get("date")
        if raw_date and hasattr(raw_date, "to_datetime"):
            tournament_data["date_display"] = raw_date.to_datetime().strftime(
                "%b %d, %Y"
            )

        match_type = tournament_data.get("matchType", "singles")
        status = tournament_data.get("status", "Active")

        # Resolve Participant Data
        participants = []
        participant_objs = tournament_data.get("participants", [])
        if participant_objs:
            user_refs = [
                (
                    obj["userRef"]
                    if "userRef" in obj
                    else db.collection("users").document(obj["user_id"])
                )
                for obj in participant_objs
                if obj and ("userRef" in obj or "user_id" in obj)
            ]
            user_docs = cast(list["DocumentSnapshot"], db.get_all(user_refs))
            users_map = {
                doc.id: {**cast(dict[str, Any], doc.to_dict()), "id": doc.id}
                for doc in user_docs
                if doc.exists
            }

            for obj in participant_objs:
                if not obj: continue
                uid = obj["userRef"].id if "userRef" in obj else obj.get("user_id")
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

        standings = get_tournament_standings(db, tournament_id, match_type)
        podium = standings[:3] if status == "Completed" else []

        # Handle Candidate Players for Invitation
        user_ref = db.collection("users").document(current_user_id)
        friends_query = user_ref.collection("friends").stream()
        friend_ids = {doc.id for doc in friends_query}

        groups_query = (
            db.collection("groups")
            .where(filter=firestore.FieldFilter("members", "array_contains", user_ref))
            .stream()
        )
        user_groups_list = []
        group_member_ids = set()
        for group_doc in groups_query:
            g_data = group_doc.to_dict()
            if g_data:
                user_groups_list.append(
                    {"id": group_doc.id, "name": g_data.get("name", "Unnamed Group")}
                )
                if "members" in g_data:
                    for m_ref in g_data["members"]:
                        group_member_ids.add(m_ref.id)

        all_potential_ids = {str(uid) for uid in (friend_ids | group_member_ids)}
        all_potential_ids.discard(str(current_user_id))

        current_participant_ids = {
            str(obj["userRef"].id if obj and "userRef" in obj else obj.get("user_id"))
            for obj in participant_objs if obj
        }
        final_invitable_ids = all_potential_ids - current_participant_ids

        invitable_users = []
        if final_invitable_ids:
            u_refs = [db.collection("users").document(uid) for uid in final_invitable_ids]
            u_docs = cast(list["DocumentSnapshot"], db.get_all(u_refs))
            for u_doc in u_docs:
                if u_doc.exists:
                    u_dict = cast(dict[str, Any], u_doc.to_dict())
                    if u_dict:
                        u_dict["id"] = u_doc.id
                        invitable_users.append(u_dict)

        invitable_users.sort(key=lambda u: smart_display_name(u).lower())

        is_owner = tournament_data.get("organizer_id") == current_user_id or (
            tournament_data.get("ownerRef")
            and tournament_data["ownerRef"].id == current_user_id
        )

        return {
            "tournament": tournament_data,
            "participants": participants,
            "standings": standings,
            "podium": podium,
            "invitable_users": invitable_users,
            "user_groups": user_groups_list,
            "is_owner": is_owner,
        }

    @staticmethod
    def invite_player(tournament_id: str, user_id: str, db: Any = None) -> None:
        """Invite a single player to the tournament."""
        if db is None:
            db = firestore.client()
        invited_ref = db.collection("users").document(user_id)
        tournament_ref = db.collection("tournaments").document(tournament_id)
        tournament_ref.update(
            {
                "participants": firestore.ArrayUnion(
                    [{"userRef": invited_ref, "status": "pending", "team_name": None}]
                ),
                "participant_ids": firestore.ArrayUnion([user_id]),
            }
        )

    @staticmethod
    def invite_group(tournament_id: str, group_id: str, db: Any = None) -> tuple[int, str]:
        """Invite all members of a group to a tournament."""
        if db is None:
            db = firestore.client()
        group_doc = cast("DocumentSnapshot", db.collection("groups").document(group_id).get())
        if not group_doc.exists:
            raise ValueError("Group not found.")

        group_data = group_doc.to_dict() or {}
        group_name = group_data.get("name", "Group")
        member_refs = group_data.get("members", [])
        
        tournament_ref = db.collection("tournaments").document(tournament_id)
        tournament_doc = cast("DocumentSnapshot", tournament_ref.get())
        tournament_data = tournament_doc.to_dict() or {}

        current_participant_ids = set(tournament_data.get("participant_ids", []))
        member_docs = cast(list["DocumentSnapshot"], db.get_all(member_refs))

        new_participants = []
        new_participant_ids = []

        for member_doc in member_docs:
            if not member_doc.exists or member_doc.id in current_participant_ids:
                continue

            m_data = member_doc.to_dict() or {}
            participant_obj = {
                "userRef": member_doc.reference,
                "status": "pending",
                "team_name": None,
            }
            if m_data.get("is_ghost") and m_data.get("email"):
                participant_obj["email"] = m_data.get("email")

            new_participants.append(participant_obj)
            new_participant_ids.append(member_doc.id)

        if new_participant_ids:
            batch = db.batch()
            batch.update(tournament_ref, {
                "participants": firestore.ArrayUnion(new_participants),
                "participant_ids": firestore.ArrayUnion(new_participant_ids),
            })
            batch.commit()

        return len(new_participant_ids), group_name

    @staticmethod
    def accept_invite(tournament_id: str, user_id: str, db: Any = None) -> bool:
        """Accept an invite to a tournament using a transaction."""
        if db is None:
            db = firestore.client()
        tournament_ref = db.collection("tournaments").document(tournament_id)

        @firestore.transactional
        def update_in_transaction(transaction, t_ref):
            snapshot = t_ref.get(transaction=transaction)
            if not snapshot.exists: return False
            participants = snapshot.get("participants")
            updated = False
            for p in participants:
                p_uid = p["userRef"].id if "userRef" in p else p.get("user_id")
                if p_uid == user_id and p["status"] == "pending":
                    p["status"] = "accepted"
                    updated = True
                    break
            if updated:
                transaction.update(t_ref, {"participants": participants})
                return True
            return False

        return update_in_transaction(db.transaction(), tournament_ref)

    @staticmethod
    def decline_invite(tournament_id: str, user_id: str, db: Any = None) -> bool:
        """Decline an invite to a tournament using a transaction."""
        if db is None:
            db = firestore.client()
        tournament_ref = db.collection("tournaments").document(tournament_id)

        @firestore.transactional
        def update_in_transaction(transaction, t_ref):
            snapshot = t_ref.get(transaction=transaction)
            if not snapshot.exists: return False
            participants = snapshot.get("participants")
            participant_ids = snapshot.get("participant_ids")
            new_participants = [
                p for p in participants
                if not ((p["userRef"].id if "userRef" in p else p.get("user_id")) == user_id and p["status"] == "pending")
            ]
            if len(new_participants) < len(participants):
                new_participant_ids = [uid for uid in participant_ids if uid != user_id]
                transaction.update(t_ref, {"participants": new_participants, "participant_ids": new_participant_ids})
                return True
            return False

        return update_in_transaction(db.transaction(), tournament_ref)

    @staticmethod
    def complete_tournament(tournament_id: str, user_id: str, db: Any = None) -> tuple[bool, str]:
        """Close tournament and send results."""
        if db is None:
            db = firestore.client()
        tournament_ref = db.collection("tournaments").document(tournament_id)
        tournament_doc = cast("DocumentSnapshot", tournament_ref.get())

        if not tournament_doc.exists: return False, "Tournament not found."
        t_data = tournament_doc.to_dict() or {}
        owner_ref = t_data.get("ownerRef")
        if not owner_ref or owner_ref.id != user_id:
            return False, "Only the organizer can complete the tournament."

        try:
            tournament_ref.update({"status": "Completed"})
            standings = get_tournament_standings(db, tournament_id, cast(str, t_data.get("matchType", "singles")))
            winner_name = standings[0]["name"] if standings else "No one"
            participants = t_data.get("participants", [])
            for p in participants:
                if p.get("status") == "accepted":
                    u_doc = p["userRef"].get()
                    if u_doc.exists:
                        user = u_doc.to_dict() or {}
                        if user.get("email"):
                            try:
                                send_email(to=user["email"], subject=f"Results: {t_data['name']}", template="email/tournament_results.html", user=user, tournament=t_data, winner_name=winner_name, standings=standings[:3])
                            except Exception as e:
                                logger.error(f"Failed to email {user['email']}: {e}")
            return True, "Tournament completed and results emailed!"
        except Exception as e:
            return False, f"An error occurred: {e}"

    @staticmethod
    def update_tournament_details(  # noqa: PLR0913
        tournament_id: str,
        user_id: str,
        name: str,
        date: datetime.date,
        location: str,
        match_type: str | None = None,
        db: Any = None,
    ) -> tuple[bool, str]:
        """Update tournament details."""
        if db is None:
            db = firestore.client()
        tournament_ref = db.collection("tournaments").document(tournament_id)
        tournament_doc = cast("DocumentSnapshot", tournament_ref.get())

        if not tournament_doc.exists: return False, "Tournament not found."
        t_data = tournament_doc.to_dict() or {}

        is_owner = t_data.get("organizer_id") == user_id or (t_data.get("ownerRef") and t_data["ownerRef"].id == user_id)
        if not is_owner: return False, "Unauthorized."

        update_data: dict[str, Any] = {
            "name": name,
            "date": datetime.datetime.combine(date, datetime.time.min),
            "location": location,
        }
        if match_type:
            is_ongoing = any(db.collection("matches").where(filter=firestore.FieldFilter("tournamentId", "==", tournament_id)).limit(1).stream())
            if not is_ongoing:
                update_data["matchType"] = match_type

        tournament_ref.update(update_data)
        return True, "Updated!"