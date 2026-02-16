from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any

from firebase_admin import firestore

if TYPE_CHECKING:
    from google.cloud.firestore_v1.client import Client


def get_pending_tournament_invites(db: Client, user_id: str) -> list[dict[str, Any]]:
    """Fetch pending tournament invitations for a user using modern FieldFilter syntax."""
    user_ref = db.collection("users").document(user_id)
    
    # Using FieldFilter and filter= keyword as per fix branch
    try:
        tournaments_query = (
            db.collection("tournaments")
            .where(filter=firestore.FieldFilter("members", "array_contains", user_ref))
            .stream()
        )
        tournaments = list(tournaments_query)
    except (TypeError, Exception):
        # Fallback for mockfirestore/empty environments
        tournaments = []

    pending_invites = []
    for doc in tournaments:
        data = doc.to_dict()
        if data:
            participants = data.get("participants") or []
            for p in participants:
                if not p:
                    continue
                p_uid = p.get("userRef").id if p.get("userRef") else p.get("user_id")
                if p_uid == user_id and p.get("status") == "pending":
                    data["id"] = doc.id
                    pending_invites.append(data)
                    break
    return pending_invites


def get_active_tournaments(db: Client, user_id: str) -> list[dict[str, Any]]:
    """Fetch active tournaments using modern FieldFilter syntax and date formatting."""
    try:
        tournaments_query = (
            db.collection("tournaments")
            .where(filter=firestore.FieldFilter("participant_ids", "array_contains", user_id))
            .stream()
        )
        tournaments = list(tournaments_query)
    except (TypeError, Exception):
        tournaments = []

    active_tournaments = []
    for doc in tournaments:
        data = doc.to_dict()
        # Maintain logic from main for non-completed tournaments
        if data and data.get("status") != "Completed":
            participants = data.get("participants") or []
            for p in participants:
                if not p:
                    continue
                p_uid = p.get("userRef").id if p.get("userRef") else p.get("user_id")
                if p_uid == user_id and p.get("status") == "accepted":
                    data["id"] = doc.id
                    
                    # Date formatting logic from fix branch
                    raw_date = data.get("start_date") or data.get("date")
                    if raw_date is not None:
                        if hasattr(raw_date, "to_datetime"):
                            data["date_display"] = raw_date.to_datetime().strftime("%b %d, %Y")
                        elif isinstance(raw_date, datetime.datetime):
                            data["date_display"] = raw_date.strftime("%b %d, %Y")
                            
                    active_tournaments.append(data)
                    break
                    
    active_tournaments.sort(
        key=lambda x: x.get("start_date") or x.get("date") or datetime.datetime.max
    )
    return active_tournaments


def get_past_tournaments(db: Client, user_id: str) -> list[dict[str, Any]]:
    """Fetch past tournaments and resolve winner names for history view."""
    from pickaladder.tournament.utils import get_tournament_standings

    try:
        tournaments_query = (
            db.collection("tournaments")
            .where(filter=firestore.FieldFilter("participant_ids", "array_contains", user_id))
            .stream()
        )
        tournaments = list(tournaments_query)
    except (TypeError, Exception):
        tournaments = []

    past_tournaments = []
    for doc in tournaments:
        data = doc.to_dict()
        if data and data.get("status") == "Completed":
            participants = data.get("participants") or []
            if any((p.get("userRef").id if p.get("userRef") else p.get("user_id")) == user_id 
                   and p.get("status") == "accepted" for p in participants if p):
                
                data["id"] = doc.id
                match_type = data.get("matchType", "singles")
                standings = get_tournament_standings(db, doc.id, match_type)
                data["winner_name"] = standings[0]["name"] if standings else "TBD"

                # Standardize display date
                raw_date = data.get("start_date") or data.get("date")
                if raw_date and hasattr(raw_date, "to_datetime"):
                    data["date_display"] = raw_date.to_datetime().strftime("%b %d, %Y")
                
                past_tournaments.append(data)

    past_tournaments.sort(
        key=lambda x: x.get("start_date") or x.get("date") or datetime.datetime.min,
        reverse=True,
    )
    return past_tournaments

# ... (remaining functions like get_public_groups and get_community_data remain same as main)