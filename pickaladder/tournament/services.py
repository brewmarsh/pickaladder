"""Service layer for tournament business logic."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from firebase_admin import firestore

from pickaladder.teams.services import TeamService
from pickaladder.user.helpers import smart_display_name
from pickaladder.utils import send_email

from .utils import get_tournament_standings

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client
    from google.cloud.firestore_v1.document import DocumentReference
    from google.cloud.firestore_v1.transaction import Transaction

MIN_PARTICIPANTS = 2


class TournamentGenerator:
    """Helper to generate tournament brackets and pairings."""

    @staticmethod
    def generate_round_robin(participant_ids: list[str]) -> list[dict[str, Any]]:
        """Generate round robin pairings using the circle method."""
        if len(participant_ids) < MIN_PARTICIPANTS:
            return []

        # Simple Circle Method implementation
        ids = list(participant_ids)
        if len(ids) % 2 != 0:
            ids.append("BYE")

        n = len(ids)
        pairings = []
        db = firestore.client()

        for _ in range(n - 1):
            for i in range(n // 2):
                p1 = ids[i]
                p2 = ids[n - 1 - i]
                if p1 != "BYE" and p2 != "BYE":
                    pairings.append(
                        {
                            "player1Ref": db.collection("users").document(p1),
                            "player2Ref": db.collection("users").document(p2),
                            "matchType": "singles",
                            "status": "PENDING",
                            "createdAt": firestore.SERVER_TIMESTAMP,
                        }
                    )
            # Rotate
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

        # Source A: Friends
        friends_query = user_ref.collection("friends").stream()
        friend_ids = {doc.id for doc in friends_query}

        # Source B: Groups
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

        owned = (
            db.collection("tournaments")
            .where(filter=firestore.FieldFilter("ownerRef", "==", user_ref))
            .stream()
        )
        participating = (
            db.collection("tournaments")
            .where(
                filter=firestore.FieldFilter(
                    "participant_ids", "array_contains", user_uid
                )
            )
            .stream()
        )

        results = {}
        for doc in owned:
            data = doc.to_dict()
            if data:
                data["id"] = doc.id
                # Formatting
                raw_date = data.get("start_date") or data.get("date")
                if raw_date and hasattr(raw_date, "to_datetime"):
                    data["date_display"] = raw_date.to_datetime().strftime("%b %d, %Y")
                results[doc.id] = data

        for doc in participating:
            if doc.id not in results:
                data = doc.to_dict()
                if data:
                    data["id"] = doc.id
                    # Formatting
                    raw_date = data.get("start_date") or data.get("date")
                    if raw_date and hasattr(raw_date, "to_datetime"):
                        data["date_display"] = raw_date.to_datetime().strftime(
                            "%b %d, %Y"
                        )
                    results[doc.id] = data

        return list(results.values())

    @staticmethod
    def _upload_banner(tournament_id: str, banner_file: Any) -> str | None:
        """Upload tournament banner to Cloud Storage."""
        if not banner_file or not getattr(banner_file, "filename", None):
            return None

        import os
        import tempfile

        from firebase_admin import storage
        from werkzeug.utils import secure_filename

        filename = secure_filename(
            banner_file.filename or f"banner_{tournament_id}.jpg"
        )
        bucket = storage.bucket()
        blob = bucket.blob(f"tournaments/{tournament_id}/{filename}")

        with tempfile.NamedTemporaryFile(suffix=os.path.splitext(filename)[1]) as tmp:
            banner_file.save(tmp.name)
            blob.upload_from_filename(tmp.name)

        blob.make_public()
        return str(blob.public_url)

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
            "date": data["date"],
            "location": data["location"],
            "matchType": data.get("matchType") or data.get("mode", "SINGLES").lower(),
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
    def _get_team_status_for_user(
        db: Client, tournament_id: str, user_uid: str
    ) -> tuple[str | None, bool]:
        """Fetch team status and pending flag for a user."""
        team_status = None
        pending_partner_invite = False
        teams_query = (
            db.collection("tournaments")
            .document(tournament_id)
            .collection("teams")
            .stream()
        )
        for doc in teams_query:
            t_team = doc.to_dict()
            if t_team["p1_uid"] == user_uid or t_team["p2_uid"] == user_uid:
                team_status = t_team["status"]
                if t_team["p2_uid"] == user_uid and t_team["status"] == "PENDING":
                    pending_partner_invite = True
                break
        return team_status, pending_partner_invite

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

        # Formatting & Participants
        raw_date = data.get("date")
        if raw_date and hasattr(raw_date, "to_datetime"):
            data["date_display"] = raw_date.to_datetime().strftime("%b %d, %Y")

        raw_participants = data.get("participants", [])
        participants = TournamentService._resolve_participants(db, raw_participants)

        # Standings, Podium & Invitable Users
        standings = get_tournament_standings(
            db, tournament_id, data.get("matchType", "singles")
        )
        podium = standings[:3] if data.get("status") == "Completed" else []

        current_p_ids = {
            str(obj.get("userRef").id if obj.get("userRef") else obj.get("user_id"))
            for obj in raw_participants
            if obj
        }
        invitable = TournamentService._get_invitable_players(
            db, user_uid, current_p_ids
        )

        # Groups & Team Status
        from pickaladder.user import UserService  # noqa: PLC0415

        user_groups = UserService.get_user_groups(db, user_uid)
        team_status, pending_partner_invite = (
            TournamentService._get_team_status_for_user(db, tournament_id, user_uid)
        )

        is_owner = data.get("organizer_id") == user_uid or (
            data.get("ownerRef") and data["ownerRef"].id == user_uid
        )

        return {
            "tournament": data,
            "participants": participants,
            "standings": standings,
            "podium": podium,
            "invitable_users": invitable,
            "user_groups": user_groups,
            "is_owner": is_owner,
            "team_status": team_status,
            "pending_partner_invite": pending_partner_invite,
        }

    @staticmethod
    def update_tournament(
        tournament_id: str,
        user_uid: str,
        update_data: dict[str, Any],
        db: Client | None = None,
    ) -> None:
        """Update tournament details with ownership check."""
        if db is None:
            db = firestore.client()
        ref = db.collection("tournaments").document(tournament_id)
        doc = cast(Any, ref.get())
        if not doc.exists:
            raise ValueError("Tournament not found.")

        data = cast(dict[str, Any], doc.to_dict())
        if not data:
            raise ValueError("Tournament data is empty.")
        owner_id = data.get("organizer_id")
        if not owner_id and data.get("ownerRef"):
            owner_id = data["ownerRef"].id

        if owner_id != user_uid:
            raise PermissionError("Unauthorized.")

        # Handle start_date / date compatibility
        if "start_date" in update_data:
            update_data["date"] = update_data["start_date"]

        # If changing match type, ensure no matches exist
        if "matchType" in update_data:
            matches = (
                db.collection("matches")
                .where(
                    filter=firestore.FieldFilter("tournamentId", "==", tournament_id)
                )
                .limit(1)
                .stream()
            )
            if any(matches):
                # Don't update matchType if matches exist
                del update_data["matchType"]

        ref.update(update_data)

    @staticmethod
    def invite_player(
        tournament_id: str, user_uid: str, invited_uid: str, db: Client | None = None
    ) -> None:
        """Invite a single player."""
        if db is None:
            db = firestore.client()

        ref = db.collection("tournaments").document(tournament_id)
        invited_ref = db.collection("users").document(invited_uid)

        ref.update(
            {
                "participants": firestore.ArrayUnion(
                    [{"userRef": invited_ref, "status": "pending", "team_name": None}]
                ),
                "participant_ids": firestore.ArrayUnion([invited_uid]),
            }
        )

    @staticmethod
    def _validate_group_invite(
        db: Client, tournament_data: dict[str, Any], group_id: str, user_uid: str
    ) -> list[Any]:
        """Validate permissions and return group member references."""
        # Check Tournament Ownership
        owner_id = tournament_data.get("organizer_id")
        if not owner_id and tournament_data.get("ownerRef"):
            owner_id = tournament_data["ownerRef"].id
        if owner_id != user_uid:
            raise PermissionError("Unauthorized.")

        # Fetch Group
        g_doc = cast(Any, db.collection("groups").document(group_id).get())
        if not g_doc.exists:
            raise ValueError("Group not found")
        g_data = cast(dict[str, Any], g_doc.to_dict())
        if not g_data:
            raise ValueError("Group data is empty")

        # Check Group Membership
        member_refs = g_data.get("members", [])
        if not any(m.id == user_uid for m in member_refs):
            raise PermissionError(
                "You can only invite members from groups you belong to."
            )
        return member_refs

    @staticmethod
    def _prepare_group_invites(
        member_docs: list[Any], current_ids: set[str]
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Filter group members and prepare invite objects."""
        new_parts = []
        new_ids = []
        for m_doc in member_docs:
            if not m_doc.exists or m_doc.id in current_ids:
                continue
            m_data = m_doc.to_dict()
            if not m_data:
                continue
            p_obj = {"userRef": m_doc.reference, "status": "pending", "team_name": None}
            if m_data.get("is_ghost") and m_data.get("email"):
                p_obj["email"] = m_data.get("email")
            new_parts.append(p_obj)
            new_ids.append(m_doc.id)
        return new_parts, new_ids

    @staticmethod
    def invite_group(
        tournament_id: str, group_id: str, user_uid: str, db: Client | None = None
    ) -> int:
        """Invite all members of a group. Returns count of new invites."""
        if db is None:
            db = firestore.client()

        t_ref = db.collection("tournaments").document(tournament_id)
        t_doc = cast(Any, t_ref.get())
        if not t_doc or not t_doc.exists:
            raise ValueError("Tournament not found")
        t_data = cast(dict[str, Any], t_doc.to_dict())

        member_refs = TournamentService._validate_group_invite(
            db, t_data, group_id, user_uid
        )
        current_ids = set(t_data.get("participant_ids", []))
        member_docs = cast(list[Any], db.get_all(member_refs))

        new_parts, new_ids = TournamentService._prepare_group_invites(
            member_docs, current_ids
        )

        if new_parts:
            t_ref.update(
                {
                    "participants": firestore.ArrayUnion(new_parts),
                    "participant_ids": firestore.ArrayUnion(new_ids),
                }
            )
        return len(new_parts)

    @staticmethod
    def accept_invite(
        tournament_id: str, user_uid: str, db: Client | None = None
    ) -> bool:
        """Accept invite via transaction."""
        if db is None:
            db = firestore.client()
        ref = db.collection("tournaments").document(tournament_id)

        @firestore.transactional
        def _tx(transaction: Transaction, t_ref: DocumentReference) -> bool:
            snap = cast(Any, t_ref.get(transaction=transaction))
            if not snap.exists:
                return False
            parts = snap.get("participants")
            updated = False
            for p in parts:
                if not p:
                    continue
                user_ref = p.get("userRef")
                uid = user_ref.id if user_ref else p.get("user_id")
                if uid == user_uid and p.get("status") == "pending":
                    p["status"] = "accepted"
                    updated = True
                    break
            if updated:
                transaction.update(t_ref, {"participants": parts})
                return True
            return False

        return _tx(db.transaction(), ref)

    @staticmethod
    def decline_invite(
        tournament_id: str, user_uid: str, db: Client | None = None
    ) -> bool:
        """Decline invite via transaction."""
        if db is None:
            db = firestore.client()
        ref = db.collection("tournaments").document(tournament_id)

        @firestore.transactional
        def _tx(transaction: Transaction, t_ref: DocumentReference) -> bool:
            snap = cast(Any, t_ref.get(transaction=transaction))
            if not snap.exists:
                return False
            parts = snap.get("participants")
            p_ids = snap.get("participant_ids")

            new_parts = []
            for p in parts:
                if not p:
                    continue
                user_ref = p.get("userRef")
                uid = user_ref.id if user_ref else p.get("user_id")
                if not (uid == user_uid and p.get("status") == "pending"):
                    new_parts.append(p)

            if len(new_parts) < len(parts):
                new_ids = [uid for uid in p_ids if uid != user_uid]
                transaction.update(
                    t_ref, {"participants": new_parts, "participant_ids": new_ids}
                )
                return True
            return False

        return _tx(db.transaction(), ref)

    @staticmethod
    def _notify_participants(
        tournament_data: dict[str, Any],
        winner_name: str,
        standings: list[dict[str, Any]],
    ) -> None:
        """Internal helper to send result emails."""
        for p in tournament_data.get("participants", []):
            if p and p.get("status") == "accepted":
                try:
                    u_doc = p.get("userRef").get() if "userRef" in p else None
                    if u_doc and u_doc.exists:
                        u_data = u_doc.to_dict()
                        if u_data and u_data.get("email"):
                            send_email(
                                to=u_data["email"],
                                subject=f"Results: {tournament_data['name']}",
                                template="email/tournament_results.html",
                                user=u_data,
                                tournament=tournament_data,
                                winner_name=winner_name,
                                standings=standings[:3],
                            )
                except Exception as e:
                    logging.error(f"Email failed: {e}")

    @staticmethod
    def complete_tournament(
        tournament_id: str, user_uid: str, db: Client | None = None
    ) -> None:
        """Finalize tournament and send emails."""
        if db is None:
            db = firestore.client()
        ref = db.collection("tournaments").document(tournament_id)
        doc = cast(Any, ref.get())
        if not doc.exists:
            raise ValueError("Tournament not found")

        data = cast(dict[str, Any], doc.to_dict())
        if not data:
            raise ValueError("Tournament data is empty")
        owner_id = data.get("organizer_id")
        if not owner_id and data.get("ownerRef"):
            owner_id = data["ownerRef"].id

        if owner_id != user_uid:
            raise PermissionError("Only the organizer can complete the tournament.")

        ref.update({"status": "Completed"})

        standings = get_tournament_standings(
            db, tournament_id, data.get("matchType", "singles")
        )
        winner = standings[0]["name"] if standings else "No one"
        TournamentService._notify_participants(data, winner, standings)

    @staticmethod
    def register_team(
        tournament_id: str,
        p1_uid: str,
        p2_uid: str | None,
        team_name: str,
        db: Client | None = None,
    ) -> str:
        """Register a team in the tournament teams sub-collection."""
        if db is None:
            db = firestore.client()

        team_data: dict[str, Any] = {
            "p1_uid": p1_uid,
            "p2_uid": p2_uid,
            "team_name": team_name,
            "status": "PENDING",
            "createdAt": firestore.SERVER_TIMESTAMP,
        }

        if p2_uid:
            # If partner is already known, link with global team ID
            team_id = TeamService.get_or_create_team(db, p1_uid, p2_uid)
            team_data["team_id"] = team_id

        ref = (
            db.collection("tournaments")
            .document(tournament_id)
            .collection("teams")
            .document()
        )
        ref.set(team_data)
        return ref.id

    @staticmethod
    def accept_team_partnership(
        tournament_id: str, user_uid: str, db: Client | None = None
    ) -> bool:
        """Accept a team partnership invitation."""
        if db is None:
            db = firestore.client()

        teams_ref = (
            db.collection("tournaments").document(tournament_id).collection("teams")
        )
        query = (
            teams_ref.where(filter=firestore.FieldFilter("p2_uid", "==", user_uid))
            .where(filter=firestore.FieldFilter("status", "==", "PENDING"))
            .stream()
        )

        updated = False
        for doc in query:
            data = doc.to_dict()
            p1_uid = data["p1_uid"]

            # Ensure global team exists and link it
            team_id = TeamService.get_or_create_team(db, p1_uid, user_uid)

            doc.reference.update({"status": "CONFIRMED", "team_id": team_id})

            TournamentService._sync_team_participants(
                db, tournament_id, p1_uid, user_uid, data.get("team_name")
            )

            updated = True

        return updated

    @staticmethod
    def _sync_team_participants(
        db: Client,
        tournament_id: str,
        p1_uid: str,
        p2_uid: str,
        team_name: str | None,
    ) -> None:
        """Ensure both team members are in the tournament participants."""
        t_ref = db.collection("tournaments").document(tournament_id)
        t_snap = cast(Any, t_ref.get())
        t_data = t_snap.to_dict()
        p_ids = t_data.get("participant_ids", [])

        new_ids = []
        new_parts = []
        for uid in [p1_uid, p2_uid]:
            if uid not in p_ids:
                new_ids.append(uid)
                new_parts.append(
                    {
                        "userRef": db.collection("users").document(uid),
                        "status": "accepted",
                        "team_name": team_name,
                    }
                )

        if new_parts:
            t_ref.update(
                {
                    "participants": firestore.ArrayUnion(new_parts),
                    "participant_ids": firestore.ArrayUnion(new_ids),
                }
            )

    @staticmethod
    def claim_team_partnership(
        tournament_id: str, team_id: str, user_uid: str, db: Client | None = None
    ) -> bool:
        """Join a placeholder team via an invite link."""
        if db is None:
            db = firestore.client()

        team_ref = (
            db.collection("tournaments")
            .document(tournament_id)
            .collection("teams")
            .document(team_id)
        )
        team_snap = cast(Any, team_ref.get())
        if not team_snap.exists:
            return False

        data = team_snap.to_dict()
        if data.get("p2_uid") or data.get("p1_uid") == user_uid:
            return False

        p1_uid = data["p1_uid"]
        global_team_id = TeamService.get_or_create_team(db, p1_uid, user_uid)

        team_ref.update(
            {"p2_uid": user_uid, "status": "CONFIRMED", "team_id": global_team_id}
        )

        TournamentService._sync_team_participants(
            db, tournament_id, p1_uid, user_uid, data.get("team_name")
        )

        return True

    @staticmethod
    def generate_bracket(tournament_id: str, db: Client | None = None) -> list[Any]:
        """Generate a tournament bracket based on participants or teams."""
        if db is None:
            db = firestore.client()

        t_ref = db.collection("tournaments").document(tournament_id)
        t_snap = cast(Any, t_ref.get())
        if not t_snap.exists:
            return []

        t_data = t_snap.to_dict()
        mode = t_data.get("mode", "SINGLES")

        bracket = []
        if mode == "SINGLES":
            participants = [
                p
                for p in t_data.get("participants", [])
                if p.get("status") == "accepted"
            ]
            for p in participants:
                u_ref = p.get("userRef")
                u_data = cast(Any, u_ref.get()).to_dict()
                bracket.append(
                    {
                        "id": u_ref.id,
                        "name": smart_display_name(u_data),
                        "type": "player",
                        "members": [u_ref.id],
                    }
                )
        else:
            # Fetch confirmed teams from sub-collection
            teams_query = (
                t_ref.collection("teams")
                .where(filter=firestore.FieldFilter("status", "==", "CONFIRMED"))
                .stream()
            )
            for doc in teams_query:
                data = doc.to_dict()
                bracket.append(
                    {
                        "id": data.get("team_id"),
                        "name": data.get("team_name"),
                        "type": "team",
                        "members": [data.get("p1_uid"), data.get("p2_uid")],
                        "tournament_team_id": doc.id,
                    }
                )
        return bracket
