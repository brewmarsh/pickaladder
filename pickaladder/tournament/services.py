"""Service layer for tournament business logic."""

from __future__ import annotations

import logging
import os
import tempfile
from typing import TYPE_CHECKING, Any, cast

from firebase_admin import firestore, storage
from werkzeug.utils import secure_filename

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
    def _resolve_single_participant(
        obj: dict[str, Any], users_map: dict[str, dict[str, Any]]
    ) -> dict[str, Any] | None:
        """Format a single participant with user data."""
        u_ref = obj.get("userRef")
        uid = u_ref.id if u_ref else obj.get("user_id")
        if uid and uid in users_map:
            u_data = users_map[uid]
            return {
                "user": u_data,
                "status": obj.get("status", "pending"),
                "display_name": smart_display_name(u_data),
                "team_name": obj.get("team_name"),
            }
        return None

    @staticmethod
    def _resolve_participants(
        db: Client, participant_objs: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Internal helper to resolve participant user data."""
        if not participant_objs:
            return []
        refs = TournamentService._get_participant_refs(db, participant_objs)
        if not refs:
            return []
        u_docs = cast(list[Any], db.get_all(refs))
        u_map = {
            doc.id: {**(doc.to_dict() or {}), "id": doc.id}
            for doc in u_docs
            if doc.exists
        }
        return [
            p
            for obj in participant_objs
            if obj
            and (p := TournamentService._resolve_single_participant(obj, u_map))
        ]

    @staticmethod
    def _get_invitable_ids(db: Client, user_uid: str) -> set[str]:
        """Fetch all friend and group member IDs for a user."""
        user_ref = db.collection("users").document(user_uid)
        f_ids = {doc.id for doc in user_ref.collection("friends").stream()}
        g_ids = set()
        groups = (
            db.collection("groups")
            .where(filter=firestore.FieldFilter("members", "array_contains", user_ref))
            .stream()
        )
        for doc in groups:
            members = (doc.to_dict() or {}).get("members")
            if members:
                for m_ref in members:
                    g_ids.add(m_ref.id)
        return (f_ids | g_ids) - {str(user_uid)}

    @staticmethod
    def _get_invitable_players(
        db: Client, user_uid: str, current_ids: set[str]
    ) -> list[dict[str, Any]]:
        """Internal helper to find invite candidates."""
        final_ids = TournamentService._get_invitable_ids(db, user_uid) - current_ids
        invitable = []
        if final_ids:
            u_refs = [db.collection("users").document(uid) for uid in final_ids]
            for doc in db.get_all(u_refs):
                if doc.exists and (data := doc.to_dict()):
                    data["id"] = doc.id
                    invitable.append(data)
        invitable.sort(key=lambda u: smart_display_name(u).lower())
        return invitable

    @staticmethod
    def _enrich_tournament(doc: Any) -> dict[str, Any]:
        """Format tournament data for display."""
        data = doc.to_dict() or {}
        data["id"] = doc.id
        raw_date = data.get("start_date") or data.get("date")
        if raw_date and hasattr(raw_date, "to_datetime"):
            data["date_display"] = raw_date.to_datetime().strftime("%b %d, %Y")
        return data

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
        parts = (
            db.collection("tournaments")
            .where(
                filter=firestore.FieldFilter(
                    "participant_ids", "array_contains", user_uid
                )
            )
            .stream()
        )
        results = {doc.id: TournamentService._enrich_tournament(doc) for doc in owned}
        for doc in parts:
            if doc.id not in results:
                results[doc.id] = TournamentService._enrich_tournament(doc)
        return list(results.values())

    @staticmethod
    def _upload_banner(t_id: str, banner: Any) -> str | None:
        """Upload tournament banner to Cloud Storage."""
        if not banner or not getattr(banner, "filename", None):
            return None
        fname = secure_filename(banner.filename or f"banner_{t_id}.jpg")
        blob = storage.bucket().blob(f"tournaments/{t_id}/{fname}")
        with tempfile.NamedTemporaryFile(suffix=os.path.splitext(fname)[1]) as tmp:
            banner.save(tmp.name)
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
        payload = {
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
        _, ref = db.collection("tournaments").add(payload)
        return str(ref.id)

    @staticmethod
    def _get_team_status_for_user(
        db: Client, t_id: str, user_uid: str
    ) -> tuple[str | None, bool]:
        """Fetch team status and pending flag for a user."""
        teams = (
            db.collection("tournaments").document(t_id).collection("teams").stream()
        )
        for doc in teams:
            t = doc.to_dict()
            if t["p1_uid"] == user_uid or t["p2_uid"] == user_uid:
                is_pending = t["p2_uid"] == user_uid and t["status"] == "PENDING"
                return t["status"], is_pending
        return None, False

    @staticmethod
    def _get_tournament_metadata(data: dict[str, Any], user_uid: str) -> dict[str, Any]:
        """Extract metadata like date display and ownership for details view."""
        raw_date = data.get("date")
        date_display = None
        if raw_date and hasattr(raw_date, "to_datetime"):
            date_display = raw_date.to_datetime().strftime("%b %d, %Y")

        owner_id = data.get("organizer_id")
        if not owner_id and data.get("ownerRef"):
            owner_id = data["ownerRef"].id
        return {"date_display": date_display, "is_owner": owner_id == user_uid}

    @staticmethod
    def get_tournament_details(
        t_id: str, user_uid: str, db: Client | None = None
    ) -> dict[str, Any] | None:
        """Fetch comprehensive details for the tournament view."""
        if db is None:
            db = firestore.client()
        doc = db.collection("tournaments").document(t_id).get()
        if not doc.exists:
            return None
        data = cast(dict[str, Any], doc.to_dict())
        data["id"] = doc.id
        meta = TournamentService._get_tournament_metadata(data, user_uid)
        from pickaladder.user import UserService  # noqa: PLC0415

        stnd = get_tournament_standings(db, t_id, data.get("matchType", "singles"))
        parts = data.get("participants", [])
        c_ids = {
            str(p.get("userRef").id if p.get("userRef") else p.get("user_id"))
            for p in parts
            if p
        }
        team_status, pending_p = TournamentService._get_team_status_for_user(
            db, t_id, user_uid
        )
        return {
            "tournament": data,
            "participants": TournamentService._resolve_participants(db, parts),
            "standings": stnd,
            "podium": stnd[:3] if data.get("status") == "Completed" else [],
            "invitable_users": TournamentService._get_invitable_players(
                db, user_uid, c_ids
            ),
            "user_groups": UserService.get_user_groups(db, user_uid),
            "is_owner": meta["is_owner"],
            "team_status": team_status,
            "pending_partner_invite": pending_p,
            "date_display": meta["date_display"],
        }

    @staticmethod
    def _get_tournament_owner_id(data: dict[str, Any]) -> str | None:
        """Resolve organizer/owner ID from tournament data."""
        o_id = data.get("organizer_id")
        if o_id:
            return o_id
        return data["ownerRef"].id if data.get("ownerRef") else None

    @staticmethod
    def _has_matches(db: Client, t_id: str) -> bool:
        """Check if any matches exist for a tournament."""
        query = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("tournamentId", "==", t_id))
            .limit(1)
            .stream()
        )
        return any(query)

    @staticmethod
    def update_tournament(
        t_id: str, uid: str, update: dict[str, Any], db: Client | None = None
    ) -> None:
        """Update tournament details with ownership check."""
        if db is None:
            db = firestore.client()
        ref = db.collection("tournaments").document(t_id)
        doc = ref.get()
        if not doc.exists:
            raise ValueError("Tournament not found.")
        data = cast(dict[str, Any], doc.to_dict())
        if not data or TournamentService._get_tournament_owner_id(data) != uid:
            raise PermissionError("Unauthorized.")
        if "start_date" in update:
            update["date"] = update["start_date"]
        if TournamentService._has_matches(db, t_id):
            for f in ["matchType", "mode", "format"]:
                update.pop(f, None)
        ref.update(update)

    @staticmethod
    def get_tournament_for_edit(
        t_id: str, uid: str, db: Client | None = None
    ) -> dict[str, Any]:
        """Fetch tournament for editing with existence and ownership checks."""
        details = TournamentService.get_tournament_details(t_id, uid, db)
        if not details:
            raise ValueError("Tournament not found.")
        if not details["is_owner"]:
            raise PermissionError("Unauthorized.")
        return cast(dict[str, Any], details["tournament"])

    @staticmethod
    def update_tournament_from_form(
        t_id: str,
        uid: str,
        fd: dict[str, Any],
        banner: Any = None,
        db: Client | None = None,
    ) -> None:
        """Update tournament using data from TournamentForm."""
        import datetime

        val = fd.get("start_date")
        if not val:
            raise ValueError("Date is required.")
        if isinstance(val, datetime.date) and not isinstance(val, datetime.datetime):
            dt = datetime.datetime.combine(val, datetime.time.min)
        else:
            dt = val
        upd = {
            "name": fd.get("name"),
            "date": dt,
            "location": fd.get("location"),
            "mode": fd.get("mode"),
            "matchType": (fd.get("mode") or "SINGLES").lower(),
        }
        if banner and getattr(banner, "filename", None):
            url = TournamentService._upload_banner(t_id, banner)
            if url:
                upd["banner_url"] = url
        TournamentService.update_tournament(t_id, uid, upd, db=db)

    @staticmethod
    def delete_tournament(t_id: str, uid: str, db: Client | None = None) -> None:
        """Delete a tournament if owner."""
        if db is None:
            db = firestore.client()
        ref = db.collection("tournaments").document(t_id)
        doc = ref.get()
        if not doc.exists:
            raise ValueError("Tournament not found")
        if TournamentService._get_tournament_owner_id(doc.to_dict() or {}) != uid:
            raise PermissionError("Unauthorized")
        ref.delete()

    @staticmethod
    def invite_player(
        t_id: str, uid: str, invited_uid: str, db: Client | None = None
    ) -> None:
        """Invite a single player."""
        if db is None:
            db = firestore.client()
        db.collection("tournaments").document(t_id).update(
            {
                "participants": firestore.ArrayUnion(
                    [
                        {
                            "userRef": db.collection("users").document(invited_uid),
                            "status": "pending",
                            "team_name": None,
                        }
                    ]
                ),
                "participant_ids": firestore.ArrayUnion([invited_uid]),
            }
        )

    @staticmethod
    def _validate_group_invite(
        db: Client, t_data: dict[str, Any], g_id: str, uid: str
    ) -> list[Any]:
        """Validate permissions and return group member references."""
        if TournamentService._get_tournament_owner_id(t_data) != uid:
            raise PermissionError("Unauthorized.")
        doc = db.collection("groups").document(g_id).get()
        if not doc.exists:
            raise ValueError("Group not found")
        refs = (doc.to_dict() or {}).get("members", [])
        if not any(m.id == uid for m in refs):
            raise PermissionError("You can only invite members from groups you belong to.")
        return refs

    @staticmethod
    def _prepare_group_invites(
        m_docs: list[DocumentSnapshot], current_ids: set[str]
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Filter group members and prepare invite objects."""
        new_p, new_ids = [], []
        for m in m_docs:
            if not m.exists or m.id in current_ids:
                continue
            d = m.to_dict() or {}
            p = {"userRef": m.reference, "status": "pending", "team_name": None}
            if d.get("is_ghost") and d.get("email"):
                p["email"] = d.get("email")
            new_p.append(p)
            new_ids.append(m.id)
        return new_p, new_ids

    @staticmethod
    def invite_group(t_id: str, g_id: str, uid: str, db: Client | None = None) -> int:
        """Invite all members of a group. Returns count of new invites."""
        if db is None:
            db = firestore.client()
        ref = db.collection("tournaments").document(t_id)
        doc = ref.get()
        if not doc.exists:
            raise ValueError("Tournament not found")
        t_data = cast(dict[str, Any], doc.to_dict())
        member_refs = TournamentService._validate_group_invite(db, t_data, g_id, uid)
        new_p, n_ids = TournamentService._prepare_group_invites(
            cast(list[Any], db.get_all(member_refs)),
            set(t_data.get("participant_ids", [])),
        )
        if new_p:
            batch = db.batch()
            batch.update(
                ref,
                {
                    "participants": firestore.ArrayUnion(new_p),
                    "participant_ids": firestore.ArrayUnion(n_ids),
                },
            )
            batch.commit()
        return len(new_p)

    @staticmethod
    def _update_status(parts: list[dict[str, Any]], uid: str, status: str) -> bool:
        """Update status of a participant in the list."""
        for p in parts:
            if not p:
                continue
            r = p.get("userRef")
            u_id = r.id if r else p.get("user_id")
            if u_id == uid and p.get("status") == "pending":
                p["status"] = status
                return True
        return False

    @staticmethod
    def accept_invite(t_id: str, uid: str, db: Client | None = None) -> bool:
        """Accept invite via transaction."""
        if db is None:
            db = firestore.client()
        ref = db.collection("tournaments").document(t_id)

        @firestore.transactional
        def _tx(tx: Transaction, t_ref: DocumentReference) -> bool:
            snap = t_ref.get(transaction=tx)
            if not snap.exists:
                return False
            parts = snap.get("participants")
            if TournamentService._update_status(parts, uid, "accepted"):
                tx.update(t_ref, {"participants": parts})
                return True
            return False

        return _tx(db.transaction(), ref)

    @staticmethod
    def _filter_participants(
        participants: list[dict[str, Any]], uid: str
    ) -> list[dict[str, Any]]:
        """Filter out a declining participant."""
        return [
            p
            for p in participants
            if p
            and not (
                (p.get("userRef").id if p.get("userRef") else p.get("user_id")) == uid
                and p.get("status") == "pending"
            )
        ]

    @staticmethod
    def decline_invite(t_id: str, uid: str, db: Client | None = None) -> bool:
        """Decline invite via transaction."""
        if db is None:
            db = firestore.client()
        ref = db.collection("tournaments").document(t_id)

        @firestore.transactional
        def _tx(tx: Transaction, t_ref: DocumentReference) -> bool:
            snap = t_ref.get(transaction=tx)
            if not snap.exists:
                return False
            parts, ids = snap.get("participants"), snap.get("participant_ids")
            new_p = TournamentService._filter_participants(parts, uid)
            if len(new_p) < len(parts):
                new_ids = [i for i in ids if i != uid]
                tx.update(t_ref, {"participants": new_p, "participant_ids": new_ids})
                return True
            return False

        return _tx(db.transaction(), ref)

    @staticmethod
    def _send_results_email(
        p: dict[str, Any], t_data: dict[str, Any], winner: str, stands: list
    ) -> None:
        """Send result email to a single participant."""
        if not p or p.get("status") != "accepted":
            return
        try:
            doc = p.get("userRef").get() if "userRef" in p else None
            if doc and doc.exists and (d := doc.to_dict()) and d.get("email"):
                send_email(
                    to=d["email"],
                    subject=f"Results: {t_data['name']}",
                    template="email/tournament_results.html",
                    user=d,
                    tournament=t_data,
                    winner_name=winner,
                    standings=stands[:3],
                )
        except Exception as e:
            logging.error(f"Email failed: {e}")

    @staticmethod
    def _notify_participants(
        t_data: dict[str, Any], winner: str, stands: list[dict[str, Any]]
    ) -> None:
        """Internal helper to send result emails."""
        for p in t_data.get("participants", []):
            TournamentService._send_results_email(p, t_data, winner, stands)

    @staticmethod
    def complete_tournament(t_id: str, uid: str, db: Client | None = None) -> None:
        """Finalize tournament and send emails."""
        if db is None:
            db = firestore.client()
        ref = db.collection("tournaments").document(t_id)
        doc = ref.get()
        if not doc.exists:
            raise ValueError("Tournament not found")
        data = cast(dict[str, Any], doc.to_dict())
        if TournamentService._get_tournament_owner_id(data) != uid:
            raise PermissionError("Only organizer can complete.")
        ref.update({"status": "Completed"})
        stands = get_tournament_standings(db, t_id, data.get("matchType", "singles"))
        winner = stands[0]["name"] if stands else "No one"
        TournamentService._notify_participants(data, winner, stands)

    @staticmethod
    def register_team(
        t_id: str, p1: str, p2: str | None, name: str, db: Client | None = None
    ) -> str:
        """Register a team in the tournament teams sub-collection."""
        if db is None:
            db = firestore.client()
        d = {
            "p1_uid": p1,
            "p2_uid": p2,
            "team_name": name,
            "status": "PENDING",
            "createdAt": firestore.SERVER_TIMESTAMP,
        }
        if p2:
            d["team_id"] = TeamService.get_or_create_team(db, p1, p2)
        ref = (
            db.collection("tournaments")
            .document(t_id)
            .collection("teams")
            .document()
        )
        ref.set(d)
        return str(ref.id)

    @staticmethod
    def accept_team_partnership(t_id: str, uid: str, db: Client | None = None) -> bool:
        """Accept a team partnership invitation."""
        if db is None:
            db = firestore.client()
        query = (
            db.collection("tournaments")
            .document(t_id)
            .collection("teams")
            .where(filter=firestore.FieldFilter("p2_uid", "==", uid))
            .where(filter=firestore.FieldFilter("status", "==", "PENDING"))
            .stream()
        )
        updated = False
        for doc in query:
            d = doc.to_dict()
            team_id = TeamService.get_or_create_team(db, d["p1_uid"], uid)
            doc.reference.update({"status": "CONFIRMED", "team_id": team_id})
            TournamentService._sync_team_participants(
                db, t_id, d["p1_uid"], uid, d.get("team_name")
            )
            updated = True
        return updated

    @staticmethod
    def _sync_team_participants(
        db: Client, t_id: str, p1: str, p2: str, name: str | None
    ) -> None:
        """Ensure both team members are in the tournament participants."""
        ref = db.collection("tournaments").document(t_id)
        ids = (ref.get().to_dict() or {}).get("participant_ids", [])
        new_ids, new_ps = [], []
        for u in [p1, p2]:
            if u not in ids:
                new_ids.append(u)
                new_ps.append(
                    {
                        "userRef": db.collection("users").document(u),
                        "status": "accepted",
                        "team_name": name,
                    }
                )
        if new_ps:
            ref.update(
                {
                    "participants": firestore.ArrayUnion(new_ps),
                    "participant_ids": firestore.ArrayUnion(new_ids),
                }
            )

    @staticmethod
    def claim_team_partnership(
        t_id: str, team_id: str, uid: str, db: Client | None = None
    ) -> bool:
        """Join a placeholder team via an invite link."""
        if db is None:
            db = firestore.client()
        ref = (
            db.collection("tournaments")
            .document(t_id)
            .collection("teams")
            .document(team_id)
        )
        snap = ref.get()
        if not snap.exists or (d := snap.to_dict()).get("p2_uid") or d.get("p1_uid") == uid:
            return False
        team_id_global = TeamService.get_or_create_team(db, d["p1_uid"], uid)
        ref.update({"p2_uid": uid, "status": "CONFIRMED", "team_id": team_id_global})
        TournamentService._sync_team_participants(db, t_id, d["p1_uid"], uid, d.get("team_name"))
        return True

    @staticmethod
    def save_pairings(t_id: str, pairings: list[dict[str, Any]]) -> int:
        """Save generated match pairings to the tournament's matches collection."""
        db = firestore.client()
        t_ref = db.collection("tournaments").document(t_id)
        batch = db.batch()
        for m in pairings:
            batch.set(t_ref.collection("matches").document(), m)
        batch.update(t_ref, {"status": "PUBLISHED"})
        batch.commit()
        return len(pairings)

    @staticmethod
    def generate_bracket(t_id: str, db: Client | None = None) -> list[Any]:
        """Generate a tournament bracket based on participants or teams."""
        if db is None:
            db = firestore.client()
        t_data = db.collection("tournaments").document(t_id).get().to_dict() or {}
        if t_data.get("mode", "SINGLES") == "SINGLES":
            accepted = [
                p for p in t_data.get("participants", []) if p.get("status") == "accepted"
            ]
            return [
                {
                    "id": p.get("userRef").id,
                    "name": smart_display_name(p.get("userRef").get().to_dict()),
                    "type": "player",
                    "members": [p.get("userRef").id],
                }
                for p in accepted
            ]
        teams = (
            db.collection("tournaments")
            .document(t_id)
            .collection("teams")
            .where(filter=firestore.FieldFilter("status", "==", "CONFIRMED"))
            .stream()
        )
        return [
            {
                "id": d.get("team_id"),
                "name": d.get("team_name"),
                "type": "team",
                "members": [d.get("p1_uid"), d.get("p2_uid")],
                "tournament_team_id": doc.id,
            }
            for doc in teams
            if (d := doc.to_dict())
        ]


class TournamentGenerator:
    """Utility class to generate tournament match pairings."""

    @staticmethod
    def _get_RR_pair_ids(ids: list[str]) -> list[tuple[str | None, str | None]]:
        """Compute Round Robin pairing IDs using the Circle Method (Pure Math)."""
        temp_ids = list(ids)
        if len(temp_ids) % 2 != 0:
            temp_ids.append(None)
        n, pairs = len(temp_ids), []
        for _ in range(n - 1):
            for i in range(n // 2):
                pairs.append((temp_ids[i], temp_ids[n - 1 - i]))
            temp_ids = [temp_ids[0]] + [temp_ids[-1]] + temp_ids[1:-1]
        return pairs

    @staticmethod
    def generate_round_robin(participant_ids: list[str]) -> list[dict[str, Any]]:
        """Generate Round Robin pairings."""
        if not participant_ids or len(participant_ids) < 2:
            return []
        db, pairings = firestore.client(), []
        for p1, p2 in TournamentGenerator._get_RR_pair_ids(list(participant_ids)):
            if p1 and p2:
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
        return pairings
