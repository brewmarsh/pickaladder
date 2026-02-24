from __future__ import annotations
import datetime
from typing import TYPE_CHECKING, Any
from firebase_admin import firestore

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client

def _is_user_participant_with_status(
    participants: list[dict[str, Any]], user_id: str, status: str
) -> bool:
    """Check if a user is in the participants list with a specific status."""
    for p in participants:
        if not p:
            continue
        user_ref = p.get("userRef")
        p_uid = (
            user_ref.id
            if user_ref is not None and hasattr(user_ref, "id")
            else p.get("user_id")
        )
        if p_uid == user_id and p.get("status") == status:
            return True
    return False

def _format_date_display(data: dict[str, Any]) -> None:
    """Format date or start_date for display in a dictionary."""
    raw_date = data.get("start_date") or data.get("date")
    if raw_date is not None:
        if hasattr(raw_date, "to_datetime"):
            data["date_display"] = raw_date.to_datetime().strftime("%b %d, %Y")
        elif isinstance(raw_date, datetime.datetime):
            data["date_display"] = raw_date.strftime("%b %d, %Y")

def _get_tournament_winner(db: Client, tournament_id: str, match_type: str) -> str:
    """Fetch the winner name for a tournament."""
    from pickaladder.tournament.utils import get_tournament_standings
    standings = get_tournament_standings(db, tournament_id, match_type)
    return standings[0]["name"] if standings else "TBD"

def get_pending_tournament_invites(db: Client, user_id: str) -> list[dict[str, Any]]:
    """Fetch pending tournament invitations for a user."""
    if not user_id:
        return []
    user_ref = db.collection("users").document(user_id)
    try:
        tournaments_query = (
            db.collection("tournaments")
            .where(filter=firestore.FieldFilter("members", "array_contains", user_ref))
            .stream()
        )
    except Exception:
        return []
    pending_invites = []
    for doc in tournaments_query:
        data = doc.to_dict()
        if data and _is_user_participant_with_status(
            data.get("participants") or [], user_id, "pending"
        ):
            data["id"] = doc.id
            pending_invites.append(data)
    return pending_invites

def get_active_tournaments(db: Client, user_id: str) -> list[dict[str, Any]]:
    """Fetch active tournaments where the user is a participant."""
    tournaments_query = (
        db.collection("tournaments")
        .where(
            filter=firestore.FieldFilter("participant_ids", "array_contains", user_id)
        )
        .stream()
    )
    active_tournaments = []
    for doc in tournaments_query:
        data = doc.to_dict()
        if data and data.get("status") != "Completed":
            if _is_user_participant_with_status(
                data.get("participants") or [], user_id, "accepted"
            ):
                data["id"] = doc.id
                _format_date_display(data)
                active_tournaments.append(data)

    active_tournaments.sort(
        key=lambda x: x.get("start_date") or x.get("date") or datetime.datetime.max
    )
    return active_tournaments

def get_past_tournaments(db: Client, user_id: str) -> list[dict[str, Any]]:
    """Fetch past (completed) tournaments for a user."""
    tournaments_query = (
        db.collection("tournaments")
        .where(
            filter=firestore.FieldFilter("participant_ids", "array_contains", user_id)
        )
        .stream()
    )
    past_tournaments = []
    for doc in tournaments_query:
        data = doc.to_dict()
        if data and data.get("status") == "Completed":
            if _is_user_participant_with_status(
                data.get("participants") or [], user_id, "accepted"
            ):
                data["id"] = doc.id
                data["winner_name"] = _get_tournament_winner(
                    db, doc.id, data.get("matchType", "singles")
                )
                _format_date_display(data)
                past_tournaments.append(data)

    past_tournaments.sort(
        key=lambda x: x.get("start_date") or x.get("date") or datetime.datetime.min,
        reverse=True,
    )
    return past_tournaments
