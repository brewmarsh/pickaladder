from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from pickaladder.utils import send_email

from .base import TournamentBase
from .invites import TournamentInvites
from .teams import TournamentTeams

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client

MIN_PARTICIPANTS = 2


class TournamentService(TournamentInvites, TournamentTeams, TournamentBase):
    """Handles business logic and data access for tournaments."""

    @staticmethod
    def _build_create_payload(
        data: dict[str, Any], user_uid: str, user_ref: Any
    ) -> dict[str, Any]:
        """Construct the initial tournament payload."""
        from firebase_admin import firestore

        m_type = data.get("matchType") or (data.get("mode") or "singles").lower()
        return {
            "name": data["name"],
            "date": data["date"],
            "venue_name": data.get("venue_name"),
            "address": data.get("address"),
            "matchType": m_type,
            "mode": m_type.upper(),
            "ownerRef": user_ref,
            "organizer_id": user_uid,
            "status": "Active",
            "participants": [{"userRef": user_ref, "status": "accepted"}],
            "participant_ids": [user_uid],
            "createdAt": firestore.SERVER_TIMESTAMP,
        }

    @staticmethod
    def create_tournament(data: dict[str, Any], user_uid: str) -> str:
        """Create a new tournament in Firestore."""
        from firebase_admin import firestore

        db = firestore.client()
        user_ref = db.collection("users").document(user_uid)
        payload = TournamentService._build_create_payload(data, user_uid, user_ref)

        _, doc_ref = db.collection("tournaments").add(payload)
        return str(doc_ref.id)

    @staticmethod
    def _has_matches(db: Client, t_id: str) -> bool:
        """Check if any matches exist for a tournament."""

        query = (
            db.collection("matches").where("tournamentId", "==", t_id).limit(1).stream()
        )
        return any(query)

    @staticmethod
    def _prepare_update_payload(
        db: Client, t_id: str, update: dict[str, Any]
    ) -> dict[str, Any]:
        """Process and sanitize the update payload."""
        if "start_date" in update:
            update["date"] = update["start_date"]

        if TournamentService._has_matches(db, t_id):
            for f in ["matchType", "mode", "format"]:
                update.pop(f, None)
        return update

    @staticmethod
    def update_tournament(
        t_id: str, uid: str, update: dict[str, Any], db: Client | None = None
    ) -> None:
        """Update tournament details with ownership check."""
        from firebase_admin import firestore

        db = db or firestore.client()
        ref = db.collection("tournaments").document(t_id)
        doc = cast(Any, ref.get())
        if not doc.exists:
            raise ValueError("Tournament not found.")

        data = cast(dict[str, Any], doc.to_dict())
        TournamentService._validate_tournament_ownership(data, uid)

        payload = TournamentService._prepare_update_payload(db, t_id, update)
        ref.update(payload)

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
    def _parse_form_date(val: Any) -> Any:
        """Convert date/datetime from form into appropriate format."""
        import datetime

        if not val:
            raise ValueError("Date is required.")
        if isinstance(val, datetime.date) and not isinstance(val, datetime.datetime):
            return datetime.datetime.combine(val, datetime.time.min)
        return val

    @staticmethod
    def _build_form_update_payload(fd: dict[str, Any]) -> dict[str, Any]:
        """Construct update dictionary from form data."""
        dt = TournamentService._parse_form_date(fd.get("start_date"))
        m_type = fd.get("match_type") or (fd.get("mode") or "singles").lower()
        return {
            "name": fd.get("name"),
            "date": dt,
            "venue_name": fd.get("venue_name"),
            "address": fd.get("address"),
            "matchType": m_type,
            "mode": m_type.upper(),
        }

    @staticmethod
    def update_tournament_from_form(
        t_id: str,
        uid: str,
        fd: dict[str, Any],
        banner: Any = None,
        db: Client | None = None,
    ) -> None:
        """Update tournament using data from TournamentForm."""
        upd = TournamentService._build_form_update_payload(fd)
        if banner and getattr(banner, "filename", None):
            url = TournamentService._upload_banner(t_id, banner)
            if url:
                upd["banner_url"] = url
        TournamentService.update_tournament(t_id, uid, upd, db=db)

    @staticmethod
    def delete_tournament(t_id: str, uid: str, db: Client | None = None) -> None:
        """Delete a tournament if owner."""
        from firebase_admin import firestore

        if db is None:
            db = firestore.client()
        ref = db.collection("tournaments").document(t_id)
        doc = cast(Any, ref.get())
        if (
            not doc.exists
            or TournamentService._get_tournament_owner_id(doc.to_dict() or {}) != uid
        ):
            raise PermissionError("Unauthorized")
        ref.delete()

    @staticmethod
    def _send_participant_email(
        user: dict[str, Any],
        t_data: dict[str, Any],
        winner: str,
        stands: list[dict[str, Any]],
    ) -> None:
        """Internal helper to send email if user has one."""
        if not user.get("email"):
            return
        send_email(
            to=user["email"],
            subject=f"Results: {t_data['name']}",
            template="email/tournament_results.html",
            user=user,
            tournament=t_data,
            winner_name=winner,
            standings=stands[:3],
        )

    @staticmethod
    def _notify_tournament_participant(
        p_data: dict[str, Any],
        t_data: dict[str, Any],
        winner: str,
        stands: list[dict[str, Any]],
    ) -> None:
        """Send result email to a single participant."""
        try:
            u_ref = p_data.get("userRef")
            doc = cast(Any, u_ref.get() if u_ref else None)
            if doc and doc.exists and (d := doc.to_dict()):
                TournamentService._send_participant_email(d, t_data, winner, stands)
        except Exception:
            logging.error("Email failed")

    @staticmethod
    def _notify_all_participants(
        data: dict[str, Any], winner: str, stands: list[dict[str, Any]]
    ) -> None:
        """Loop through participants and send result emails."""
        for p in data.get("participants", []):
            if p and p.get("status") == "accepted":
                TournamentService._notify_tournament_participant(
                    p, data, winner, stands
                )

    @staticmethod
    def complete_tournament(t_id: str, uid: str, db: Client | None = None) -> None:
        """Finalize tournament and send emails."""
        from firebase_admin import firestore

        from pickaladder.tournament.utils import get_tournament_standings

        db = db or firestore.client()
        ref = db.collection("tournaments").document(t_id)
        doc = cast(Any, ref.get())
        if not doc or not doc.exists:
            raise ValueError("Tournament not found")

        data = cast(dict[str, Any], doc.to_dict())
        TournamentService._validate_tournament_ownership(data, uid)

        ref.update({"status": "Completed"})
        stands = get_tournament_standings(db, t_id, data.get("matchType", "singles"))
        winner = stands[0]["name"] if stands else "No one"
        TournamentService._notify_all_participants(data, winner, stands)

    @staticmethod
    def _prepare_match_pairing(
        m: dict[str, Any], t_id: str, t_date: Any
    ) -> dict[str, Any]:
        """Enrich a match pairing with tournament metadata."""
        m["tournamentId"] = t_id
        m["matchDate"] = m.get("matchDate") or t_date
        return m

    @staticmethod
    def save_pairings(t_id: str, pairings: list[dict[str, Any]]) -> int:
        """Save generated match pairings to the global matches collection."""
        from firebase_admin import firestore

        db = firestore.client()
        t_ref = db.collection("tournaments").document(t_id)
        t_snap = cast(Any, t_ref.get())
        t_data = t_snap.to_dict() or {}
        t_date = t_data.get("date") or firestore.SERVER_TIMESTAMP

        batch = db.batch()
        for m in pairings:
            match_doc = TournamentService._prepare_match_pairing(m, t_id, t_date)
            batch.set(db.collection("matches").document(), match_doc)

        batch.update(t_ref, {"status": "PUBLISHED"})
        batch.commit()
        return len(pairings)

    @staticmethod
    def _gen_singles_bracket(
        db: Client, t_data: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Generate bracket data for singles tournament."""
        participants = TournamentService._resolve_participants(
            db, t_data.get("participants", [])
        )
        return [
            {
                "id": p["user"]["id"],
                "name": p["display_name"],
                "type": "player",
                "members": [p["user"]["id"]],
            }
            for p in participants
            if p["status"] == "accepted"
        ]

    @staticmethod
    def _map_team_to_bracket_item(doc: Any) -> dict[str, Any] | None:
        """Map a team document to a bracket item."""
        d = doc.to_dict()
        if not d:
            return None
        return {
            "id": d.get("team_id"),
            "name": d.get("team_name"),
            "type": "team",
            "members": [d.get("p1_uid"), d.get("p2_uid")],
            "tournament_team_id": doc.id,
        }

    @staticmethod
    def _gen_doubles_bracket(db: Client, t_id: str) -> list[dict[str, Any]]:
        """Generate bracket data for doubles tournament."""

        teams = (
            db.collection("tournaments")
            .document(t_id)
            .collection("teams")
            .where("status", "==", "CONFIRMED")
            .stream()
        )
        return [
            item
            for doc in teams
            if (item := TournamentService._map_team_to_bracket_item(doc))
        ]

    @staticmethod
    def generate_bracket(t_id: str, db: Client | None = None) -> list[Any]:
        """Generate a tournament bracket based on participants or teams."""
        from firebase_admin import firestore

        db = db or firestore.client()
        doc = cast(Any, db.collection("tournaments").document(t_id).get())
        if not doc or not doc.exists:
            return []
        t_data = doc.to_dict() or {}
        m_type = (t_data.get("matchType") or t_data.get("mode", "singles")).lower()
        if m_type == "singles":
            return TournamentService._gen_singles_bracket(db, t_data)
        return TournamentService._gen_doubles_bracket(db, t_id)

    @staticmethod
    def _check_user_in_team(
        user_uid: str, team_data: dict[str, Any]
    ) -> tuple[str | None, bool] | None:
        """Check if user is in team and return status/pending flag."""
        if team_data.get("p1_uid") == user_uid or team_data.get("p2_uid") == user_uid:
            is_pending = (
                team_data.get("p2_uid") == user_uid
                and team_data.get("status") == "PENDING"
            )
            return cast(str, team_data.get("status")), is_pending
        return None

    @staticmethod
    def _get_team_status_for_user(
        db: Client, t_id: str, user_uid: str
    ) -> tuple[str | None, bool]:
        """Fetch team status and pending flag for a user."""
        teams = db.collection("tournaments").document(t_id).collection("teams").stream()
        for doc in teams:
            res = TournamentService._check_user_in_team(
                user_uid, cast(dict[str, Any], doc.to_dict())
            )
            if res:
                return res
        return None, False

    @staticmethod
    def get_tournament_details(
        t_id: str, uid: str, db: Client | None = None
    ) -> dict[str, Any] | None:
        """Fetch full tournament details including participants and standings."""
        from firebase_admin import firestore

        from pickaladder.tournament.utils import get_tournament_standings
        from pickaladder.user import UserService

        db = db or firestore.client()
        ref = db.collection("tournaments").document(t_id)
        doc = cast(Any, ref.get())
        if not doc or not doc.exists:
            return None

        data = TournamentService._enrich_tournament(doc)
        meta = TournamentBase._get_tournament_metadata(data, uid)

        parts = data.get("participants", [])
        resolved_parts = TournamentService._resolve_participants(db, parts)
        stands = get_tournament_standings(db, t_id, data.get("matchType", "singles"))
        c_ids = TournamentService._extract_participant_ids(parts)
        t_stat, pend = TournamentService._get_team_status_for_user(db, t_id, uid)

        return {
            "tournament": data,
            "participants": resolved_parts,
            "standings": stands,
            "podium": stands[:3] if data.get("status") == "Completed" else [],
            "invitable_users": TournamentService._get_invitable_players(db, uid, c_ids),
            "user_groups": UserService.get_user_groups(db, uid),
            "team_status": t_stat,
            "pending_partner_invite": pend,
            **meta,
        }
