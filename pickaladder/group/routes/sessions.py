"""Session routes for the group blueprint."""

from __future__ import annotations

from typing import Any

from firebase_admin import firestore
from flask import Response, flash, g, redirect, render_template, url_for

from pickaladder.auth.decorators import login_required
from pickaladder.group import bp
from pickaladder.group.services.session_service import SessionService


@bp.route("/session/<string:session_id>/quick-log", methods=["GET"])
@login_required
def quick_log(session_id: str) -> Response | str | dict[str, Any]:
    """Display the mobile-optimized quick log for a session."""
    db = firestore.client()
    session_data = SessionService.get_session(db, session_id)
    if not session_data:
        flash("Session not found", "danger")
        return redirect(url_for(".view_groups"))  # type: ignore

    # Batch fetch players and group
    all_refs = []
    player_ids = session_data.get("playerIds", [])
    if player_ids:
        all_refs.extend([db.collection("users").document(pid) for pid in player_ids])

    group_ref = db.collection("groups").document(session_data["groupId"])
    all_refs.append(group_ref)

    docs_map = {doc.reference: doc for doc in db.get_all(all_refs)}

    players = []
    if player_ids:
        for pid in player_ids:
            player_ref = db.collection("users").document(pid)
            player_doc = docs_map.get(player_ref)
            if player_doc and player_doc.exists:
                p_data = player_doc.to_dict() or {}
                p_data["id"] = player_doc.id
                players.append(p_data)

    group_name = "Group"
    group_doc = docs_map.get(group_ref)
    if group_doc and group_doc.exists:
        group_name = (group_doc.to_dict() or {}).get("name", "Group")

    return render_template(
        "group/quick_log.html",
        session=session_data,
        players=players,
        session_id=session_id,
        group_name=group_name,
    )


@bp.route("/session/<string:session_id>", methods=["GET"])
@login_required
def view_session(session_id: str) -> Response | str | dict[str, Any]:
    """Display session summary and matches."""
    db = firestore.client()
    session_data = SessionService.get_session(db, session_id)
    if not session_data:
        flash("Session not found", "danger")
        return redirect(url_for(".view_groups"))  # type: ignore

    # Batch fetch matches, players, and group
    all_refs = []

    match_ids = session_data.get("matchIds", [])
    if match_ids:
        all_refs.extend([db.collection("matches").document(mid) for mid in match_ids])

    player_ids = session_data.get("playerIds", [])
    if player_ids:
        all_refs.extend([db.collection("users").document(pid) for pid in player_ids])

    group_ref = db.collection("groups").document(session_data["groupId"])
    all_refs.append(group_ref)

    docs_map = {doc.reference: doc for doc in db.get_all(all_refs)}

    matches = []
    if match_ids:
        for mid in match_ids:
            match_ref = db.collection("matches").document(mid)
            match_doc = docs_map.get(match_ref)
            if match_doc and match_doc.exists:
                m_data = match_doc.to_dict() or {}
                m_data["id"] = match_doc.id
                matches.append(m_data)

    players = {}
    if player_ids:
        for pid in player_ids:
            player_ref = db.collection("users").document(pid)
            player_doc = docs_map.get(player_ref)
            if player_doc and player_doc.exists:
                p_data = player_doc.to_dict() or {}
                p_data["id"] = player_doc.id
                players[player_doc.id] = p_data

    group_name = "Group"
    group_doc = docs_map.get(group_ref)
    if group_doc and group_doc.exists:
        group_name = (group_doc.to_dict() or {}).get("name", "Group")

    return render_template(
        "group/session_view.html",
        session=session_data,
        matches=matches,
        players=players,
        session_id=session_id,
        group_name=group_name,
    )


@bp.route("/session/<string:session_id>/verify", methods=["POST"])
@login_required
def verify_session(session_id: str) -> Response | str | dict[str, Any]:
    """Trigger batch verification for a session."""
    db = firestore.client()
    success = SessionService.verify_session(db, session_id, g.user.uid)
    if success:
        flash("Session verified!", "success")
    else:
        flash("Failed to verify session. You may not be a participant.", "danger")

    return redirect(url_for(".view_session", session_id=session_id))  # type: ignore
