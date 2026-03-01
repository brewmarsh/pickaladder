from __future__ import annotations

import os
import tempfile
from collections import UserDict
from typing import TYPE_CHECKING, Any, cast

from flask import current_app
from werkzeug.utils import secure_filename

from pickaladder.user.helpers import smart_display_name

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client
    from google.cloud.firestore_v1.document import DocumentReference

    from pickaladder.tournament.models import Tournament


class TournamentBase:
    """Base class with shared helpers for tournament services."""

    @staticmethod
    def _enrich_tournament(doc: Any) -> Tournament:
        """Format tournament data for display."""
        from pickaladder.tournament.models import Tournament

        import datetime

        data = cast(dict[str, Any], doc.to_dict() or {})
        data["id"] = doc.id
        raw_date = data.get("start_date") or data.get("date")

        if raw_date:
            if hasattr(raw_date, "to_datetime"):
                data["date_display"] = raw_date.to_datetime().strftime("%b %d, %Y")
            elif isinstance(raw_date, (datetime.datetime, datetime.date)):
                data["date_display"] = raw_date.strftime("%b %d, %Y")

        # Compatibility for legacy templates using 'location' instead of 'venue_name'
        if "venue_name" in data and not data.get("location"):
            data["location"] = data["venue_name"]

        return Tournament(data)

    @staticmethod
    def _get_tournament_owner_id(data: dict[str, Any] | UserDict) -> str | None:
        """Resolve organizer/owner ID from tournament data."""
        o_id = data.get("organizer_id")
        if o_id:
            return cast(str, o_id)
        owner_ref = data.get("ownerRef")
        return getattr(owner_ref, "id", None) if owner_ref else None

    @staticmethod
    def _get_tournament_metadata(
        data: dict[str, Any] | UserDict, user_uid: str
    ) -> dict[str, Any]:
        """Extract metadata like date display and ownership for details view."""
        raw_date = data.get("date")
        date_display = None
        if raw_date and hasattr(raw_date, "to_datetime"):
            date_display = raw_date.to_datetime().strftime("%b %d, %Y")

        owner_id = TournamentBase._get_tournament_owner_id(data)
        return {"date_display": date_display, "is_owner": owner_id == user_uid}

    @staticmethod
    def _extract_participant_ids(participants: list[dict[str, Any]]) -> set[str]:
        """Extract user IDs from participants list."""
        return {
            str(
                getattr(p.get("userRef"), "id", p.get("user_id"))
                if p.get("userRef")
                else p.get("user_id")
            )
            for p in participants
            if p
        }

    @staticmethod
    def _fetch_owned_tournaments(db: Client, user_ref: Any) -> list[Any]:
        """Query tournaments owned by the user."""
        from firebase_admin import firestore

        return list(
            db.collection("tournaments")
            .where(filter=firestore.FieldFilter("ownerRef", "==", user_ref))
            .stream()
        )

    @staticmethod
    def _fetch_participating_tournaments(db: Client, user_uid: str) -> list[Any]:
        """Query tournaments where the user is a participant."""
        from firebase_admin import firestore

        return list(
            db.collection("tournaments")
            .where(
                filter=firestore.FieldFilter(
                    "participant_ids", "array_contains", user_uid
                )
            )
            .stream()
        )

    @staticmethod
    def _process_participating_tournaments(
        results: dict[str, Tournament], participating: list[Any]
    ) -> dict[str, Tournament]:
        """Add participating tournaments to the results if not already present."""
        for d in participating:
            if d.id not in results:
                results[d.id] = TournamentBase._enrich_tournament(d)
        return results

    @staticmethod
    def _merge_tournament_results(
        owned: list[Any], participating: list[Any]
    ) -> list[Tournament]:
        """Merge owned and participating tournaments into a single list."""
        results: dict[str, Tournament] = {
            d.id: TournamentBase._enrich_tournament(d) for d in owned
        }
        results = TournamentBase._process_participating_tournaments(
            results, participating
        )
        return list(results.values())

    @staticmethod
    def list_tournaments(user_uid: str, db: Client | None = None) -> list[Tournament]:
        """Fetch all tournaments for a user."""
        from pickaladder.tournament import services as ts

        db = db or ts.firestore.client()
        u_ref = db.collection("users").document(user_uid)
        owned = TournamentBase._fetch_owned_tournaments(db, u_ref)
        parts = TournamentBase._fetch_participating_tournaments(db, user_uid)

        return TournamentBase._merge_tournament_results(owned, parts)

    @staticmethod
    def _get_storage_bucket_name() -> str:
        """Resolve the Firebase storage bucket name."""
        try:
            return current_app.config.get(
                "FIREBASE_STORAGE_BUCKET", "pickaladder.firebasestorage.app"
            )
        except RuntimeError:
            return "pickaladder.firebasestorage.app"

    @staticmethod
    def _upload_banner(t_id: str, banner: Any) -> str | None:
        """Upload tournament banner to Cloud Storage."""
        from firebase_admin import storage

        if not banner or not getattr(banner, "filename", None):
            return None
        fname = secure_filename(banner.filename or f"banner_{t_id}.jpg")
        b_name = TournamentBase._get_storage_bucket_name()

        blob = storage.bucket(b_name).blob(f"tournaments/{t_id}/{fname}")
        with tempfile.NamedTemporaryFile(suffix=os.path.splitext(fname)[1]) as tmp:
            banner.save(tmp.name)
            blob.upload_from_filename(tmp.name)
        blob.make_public()
        return str(blob.public_url)

    @staticmethod
    def _map_single_participant_ref(
        db: Client, obj: dict[str, Any]
    ) -> DocumentReference | None:
        """Map a single participant object to a user reference."""
        if not obj:
            return None
        if obj.get("userRef"):
            return cast("DocumentReference", obj["userRef"])
        if obj.get("user_id"):
            return cast(
                "DocumentReference",
                db.collection("users").document(cast(str, obj["user_id"])),
            )
        return None

    @staticmethod
    def _get_participant_refs(
        db: Client, participant_objs: list[dict[str, Any]]
    ) -> list[DocumentReference]:
        """Extract user references from participant objects."""
        return [
            ref
            for obj in participant_objs
            if (ref := TournamentBase._map_single_participant_ref(db, obj))
        ]

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
    def _build_user_map(
        db: Client, refs: list[DocumentReference]
    ) -> dict[str, dict[str, Any]]:
        """Fetch users and build a map by ID."""
        u_docs = cast(list[Any], db.get_all(refs))
        return {
            doc.id: {**(doc.to_dict() or {}), "id": doc.id}
            for doc in u_docs
            if doc.exists
        }

    @staticmethod
    def _resolve_participants(
        db: Client, participant_objs: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Internal helper to resolve participant user data."""
        if not participant_objs:
            return []
        refs = TournamentBase._get_participant_refs(db, participant_objs)
        if not refs:
            return []

        u_map = TournamentBase._build_user_map(db, refs)

        return [
            p
            for obj in participant_objs
            if (p := TournamentBase._resolve_single_participant(obj, u_map))
        ]

    @staticmethod
    def _validate_tournament_ownership(data: dict[str, Any], user_uid: str) -> None:
        """Raise PermissionError if user is not the tournament owner."""
        if TournamentBase._get_tournament_owner_id(data) != user_uid:
            raise PermissionError("Unauthorized access to tournament.")
