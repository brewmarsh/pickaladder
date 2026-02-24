from __future__ import annotations

import logging
import os
import tempfile
from typing import TYPE_CHECKING, Any, cast

from flask import current_app
from werkzeug.utils import secure_filename

from pickaladder.user.helpers import smart_display_name
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
    def _enrich_tournament(doc: Any) -> dict[str, Any]:
        """Format tournament data for display."""
        data = cast(dict[str, Any], doc.to_dict() or {})
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
        from firebase_admin import firestore

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
        from firebase_admin import storage

        if not banner or not getattr(banner, "filename", None):
            return None
        fname = secure_filename(banner.filename or f"banner_{t_id}.jpg")
        try:
            bucket_name = current_app.config.get(
                "FIREBASE_STORAGE_BUCKET", "pickaladder.firebasestorage.app"
            )
        except RuntimeError:
            bucket_name = "pickaladder.firebasestorage.app"

        blob = storage.bucket(bucket_name).blob(f"tournaments/{t_id}/{fname}")
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
        from firebase_admin import firestore

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
        teams = db.collection("tournaments").document(t_id).collection("teams").stream()
        for doc in teams:
            t = cast(dict[str, Any], doc.to_dict())
            if t["p1_uid"] == user_uid or t["p2_uid"] == user_uid:
                is_pending = t["p2_uid"] == user_uid and t["status"] == "PENDING"
                return cast(str, t["status"]), is_pending
        return None, False

    @staticmethod
    def _get_tournament_metadata(data: dict[str, Any], user_uid: str) -> dict[str, Any]:
        """Extract metadata like date display and ownership for details view."""
        raw_date = data.get("date")
        date_display = None
        if raw_date and hasattr(raw_date, "to_datetime"):
            date_display = raw_date.to_datetime().strftime("%b %d, %Y")

        owner_id = TournamentService._get_tournament_owner_id(data)
        return {"date_display": date_display, "is_owner": owner_id == user_uid}

    @staticmethod
    def get_tournament_details(
        t_id: str, user_uid: str, db: Client | None = None
    ) -> dict[str, Any] | None:
        """Fetch comprehensive details for the tournament view."""
        from firebase_admin import firestore

        from pickaladder.tournament.utils import get_tournament_standings

        if db is None:
            db = firestore.client()
        doc = cast(Any, db.collection("tournaments").document(t_id).get())
        if not doc.exists:
            return None
        data = cast(dict[str, Any], doc.to_dict())
        data["id"] = doc.id
        meta = TournamentService._get_tournament_metadata(data, user_uid)
        from pickaladder.user import UserService  # noqa: PLC0415

        stnd = get_tournament_standings(db, t_id, data.get("matchType", "singles"))
        parts = data.get("participants", [])
        c_ids = {
            str(
                getattr(p.get("userRef"), "id", p.get("user_id"))
                if p.get("userRef")
                else p.get("user_id")
            )
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
    def _has_matches(db: Client, t_id: str) -> bool:
        """Check if any matches exist for a tournament."""
        from firebase_admin import firestore

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
        from firebase_admin import firestore

        if db is None:
            db = firestore.client()
        ref = db.collection("tournaments").document(t_id)
        doc = cast(Any, ref.get())
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
    def complete_tournament(t_id: str, uid: str, db: Client | None = None) -> None:
        """Finalize tournament and send emails."""
        from firebase_admin import firestore

        from pickaladder.tournament.utils import get_tournament_standings

        if db is None:
            db = firestore.client()
        ref = db.collection("tournaments").document(t_id)
        doc = cast(Any, ref.get())
        if not doc.exists:
            raise ValueError("Tournament not found")
        data = cast(dict[str, Any], doc.to_dict())
        if TournamentService._get_tournament_owner_id(data) != uid:
            raise PermissionError("Only organizer can complete.")
        ref.update({"status": "Completed"})
        stands = get_tournament_standings(db, t_id, data.get("matchType", "singles"))
        winner = stands[0]["name"] if stands else "No one"
        for p in data.get("participants", []):
            if not p or p.get("status") != "accepted":
                continue
            try:
                u_ref = p.get("userRef")
                doc = cast(Any, u_ref.get() if u_ref else None)
                if doc and doc.exists and (d := doc.to_dict()) and d.get("email"):
                    send_email(
                        to=d["email"],
                        subject=f"Results: {data['name']}",
                        template="email/tournament_results.html",
                        user=d,
                        tournament=data,
                        winner_name=winner,
                        standings=stands[:3],
                    )
            except Exception:
                logging.error("Email failed")

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
            m["tournamentId"] = t_id
            m["matchDate"] = m.get("matchDate") or t_date
            batch.set(db.collection("matches").document(), m)

        batch.update(t_ref, {"status": "PUBLISHED"})
        batch.commit()
        return len(pairings)

    @staticmethod
    def generate_bracket(t_id: str, db: Client | None = None) -> list[Any]:
        """Generate a tournament bracket based on participants or teams."""
        from firebase_admin import firestore

        if db is None:
            db = firestore.client()
        doc = cast(Any, db.collection("tournaments").document(t_id).get())
        t_data = doc.to_dict() or {}
        if t_data.get("mode", "SINGLES") == "SINGLES":
            accepted = [
                p
                for p in t_data.get("participants", [])
                if p.get("status") == "accepted"
            ]
            return [
                {
                    "id": getattr(p.get("userRef"), "id", p.get("user_id")),
                    "name": smart_display_name(
                        cast(Any, p.get("userRef").get()).to_dict()
                    ),
                    "type": "player",
                    "members": [getattr(p.get("userRef"), "id", p.get("user_id"))],
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
