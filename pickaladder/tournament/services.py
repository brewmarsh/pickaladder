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
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client
    from google.cloud.firestore_v1.document import DocumentReference
    from google.cloud.firestore_v1.transaction import Transaction


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
            return participant_objs

        user_docs = db.get_all(user_refs)
        users_map = {
            doc.id: {"id": doc.id, **(doc.to_dict() or {})}
            for doc in user_docs
            if doc.exists
        }

        resolved = []
        for obj in participant_objs:
            if not obj:
                continue
            uid = obj.get("userRef").id if obj.get("userRef") else obj.get("user_id")
            user_info = users_map.get(uid, {})
            resolved.append(
                {
                    **obj,
                    "user": user_info,
                    "display_name": smart_display_name(user_info)
                    or obj.get("email", "Unknown"),
                }
            )
        return resolved

    @staticmethod
    def create_tournament(
        data: dict[str, Any], user_uid: str, db: Client | None = None
    ) -> str:
        """Create a new tournament and return its ID."""
        if db is None:
            db = firestore.client()
        user_ref = db.collection("users").document(user_uid)

        tournament_payload = {
            **data,
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
    def update_tournament(
        tournament_id: str,
        user_uid: str,
        update_data: dict[str, Any],
        db: Client | None = None,
    ) -> None:
        """Update tournament details with permission check."""
        if db is None:
            db = firestore.client()

        ref = db.collection("tournaments").document(tournament_id)
        doc = cast(Any, ref.get())
        if not doc.exists:
            raise ValueError("Tournament not found")

        data = doc.to_dict() or {}
        if data.get("organizer_id") != user_uid and (
            not data.get("ownerRef") or data["ownerRef"].id != user_uid
        ):
            raise PermissionError("Unauthorized")

        # Basic validation: check if matches already exist
        matches = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("tournamentId", "==", tournament_id))
            .limit(1)
            .stream()
        )
        if any(matches):
            # Only allow certain fields to be updated if matches exist
            allowed = ["name", "description", "banner_url", "location_data"]
            update_data = {k: v for k, v in update_data.items() if k in allowed}
            if not update_data:
                return

        ref.update(update_data)

    @staticmethod
    def delete_tournament(
        tournament_id: str, user_uid: str, db: Client | None = None
    ) -> None:
        """Delete a tournament and its sub-collections."""
        if db is None:
            db = firestore.client()

        ref = db.collection("tournaments").document(tournament_id)
        doc = cast(Any, ref.get())
        if not doc.exists:
            return

        data = doc.to_dict() or {}
        if data.get("organizer_id") != user_uid and (
            not data.get("ownerRef") or data["ownerRef"].id != user_uid
        ):
            raise PermissionError("Unauthorized")

        # In a real app, we'd delete sub-collections too. For now, just delete the doc.
        ref.delete()

    @staticmethod
    def list_tournaments(user_uid: str, db: Client | None = None) -> list[dict[str, Any]]:
        """List tournaments relevant to the user."""
        if db is None:
            db = firestore.client()

        # Simplified query: all tournaments (for discovery)
        docs = db.collection("tournaments").order_by("date").stream()
        tournaments = []
        for doc in docs:
            d = doc.to_dict() or {}
            d["id"] = doc.id
            raw_date = d.get("date")
            if raw_date and hasattr(raw_date, "to_datetime"):
                d["date_display"] = raw_date.to_datetime().strftime("%b %d, %Y")
            tournaments.append(d)
        return tournaments

    @staticmethod
    def _get_invitable_players(
        db: Client, user_uid: str, current_ids: set[str]
    ) -> list[dict[str, Any]]:
        """Find friends and group members who are not yet in the tournament."""
        # 1. Friends
        friend_docs = db.collection("users").document(user_uid).collection("friends").stream()
        friend_ids = {doc.id for doc in friend_docs if doc.to_dict().get("status") == "accepted"}

        # 2. Group Members
        groups_query = db.collection("groups").where(filter=firestore.FieldFilter("members", "array_contains", db.collection("users").document(user_uid))).stream()
        group_member_ids = set()
        for g_doc in groups_query:
            g_data = g_doc.to_dict() or {}
            for m_ref in g_data.get("members", []):
                group_member_ids.add(m_ref.id)

        all_candidate_ids = (friend_ids | group_member_ids) - current_ids - {user_uid}
        if not all_candidate_ids:
            return []

        candidates = []
        c_refs = [db.collection("users").document(uid) for uid in all_candidate_ids]
        for c_doc in db.get_all(c_refs):
            if c_doc.exists:
                c_data = c_doc.to_dict() or {}
                c_data["id"] = c_doc.id
                candidates.append(c_data)
        return candidates

    @staticmethod
    def _upload_banner(tournament_id: str, file_obj: Any) -> str | None:
        """Upload tournament banner to Firebase Storage (stub)."""
        # In a real app, this would use firebase_admin.storage
        return f"/static/banners/tournament_{tournament_id}.jpg"

    @staticmethod
    def invite_player(
        tournament_id: str, organizer_uid: str, invited_uid: str, db: Client | None = None
    ) -> None:
        """Invite a single player."""
        if db is None:
            db = firestore.client()

        t_ref = db.collection("tournaments").document(tournament_id)
        p_obj = {
            "userRef": db.collection("users").document(invited_uid),
            "status": "pending",
        }
        t_ref.update({
            "participants": firestore.ArrayUnion([p_obj]),
            "participant_ids": firestore.ArrayUnion([invited_uid]),
        })

    @staticmethod
    def _validate_group_invite(
        db: Client, t_data: dict[str, Any], group_id: str, user_uid: str
    ) -> list[DocumentReference]:
        """Verify permissions and return group member references."""
        if t_data.get("organizer_id") != user_uid and (
            not t_data.get("ownerRef") or t_data["ownerRef"].id != user_uid
        ):
            raise PermissionError("Unauthorized")

        g_doc = db.collection("groups").document(group_id).get()
        if not g_doc.exists:
            raise ValueError("Group not found")

        g_data = g_doc.to_dict() or {}
        return g_data.get("members", [])

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
            p_obj = {"userRef": m_doc.reference, "status": "pending"}
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
            # Use batch as expected by tests
            batch = db.batch()
            batch.update(t_ref, {
                "participants": firestore.ArrayUnion(new_parts),
                "participant_ids": firestore.ArrayUnion(new_ids),
            })
            batch.commit()
        return len(new_parts)

    @staticmethod
    def accept_invite(
        tournament_id: str, user_uid: str, db: Client | None = None
    ) -> bool:
        """Accept an invite."""
        if db is None:
            db = firestore.client()
        ref = db.collection("tournaments").document(tournament_id)

        @firestore.transactional
        def _tx(transaction: Transaction, t_ref: DocumentReference) -> bool:
            t_snap = t_ref.get(transaction=transaction)
            if not t_snap.exists:
                return False
            data = t_snap.to_dict() or {}
            parts = data.get("participants", [])
            updated = False
            for p in parts:
                uid = p.get("userRef").id if p.get("userRef") else p.get("user_id")
                if uid == user_uid and p.get("status") == "pending":
                    p["status"] = "accepted"
                    updated = True
                    break
            if updated:
                transaction.update(t_ref, {"participants": parts})
            return updated

        return _tx(db.transaction(), ref)

    @staticmethod
    def decline_invite(
        tournament_id: str, user_uid: str, db: Client | None = None
    ) -> bool:
        """Decline/Remove an invite."""
        if db is None:
            db = firestore.client()
        ref = db.collection("tournaments").document(tournament_id)

        @firestore.transactional
        def _tx(transaction: Transaction, t_ref: DocumentReference) -> bool:
            t_snap = t_ref.get(transaction=transaction)
            if not t_snap.exists:
                return False
            data = t_snap.to_dict() or {}
            parts = data.get("participants", [])
            p_ids = data.get("participant_ids", [])
            new_parts = []
            for p in parts:
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


class TournamentGenerator:
    """Handles pairing generation for tournaments."""

    MIN_PARTICIPANTS = 2

    @staticmethod
    def generate_round_robin(participants: list[Any]) -> list[dict[str, Any]]:
        """Generate round robin pairings using the circle method."""
        if len(participants) < TournamentGenerator.MIN_PARTICIPANTS:
            return []

        if len(participants) % 2 != 0:
            participants.append(None)  # Add a bye

        n = len(participants)
        rounds = []
        p = list(participants)

        for _ in range(n - 1):
            matches = []
            for i in range(n // 2):
                if p[i] is not None and p[n - 1 - i] is not None:
                    matches.append({"p1": p[i], "p2": p[n - 1 - i]})
            rounds.append(matches)
            # Rotate participants, keeping the first one fixed
            p = [p[0]] + [p[-1]] + p[1:-1]

        # Flatten matches for saving to sub-collection
        all_matches = []
        for r in rounds:
            all_matches.extend(r)
        return all_matches
