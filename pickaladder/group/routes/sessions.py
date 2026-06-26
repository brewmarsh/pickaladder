"""Session routes for the group blueprint."""

from __future__ import annotations

from firebase_admin import firestore
from flask import flash, g, redirect, render_template, url_for

from pickaladder.auth.decorators import login_required
from pickaladder.group import bp
from pickaladder.group.services.session_service import SessionService


@bp.route("/session/<string:session_id>/quick-log", methods=["GET"])
@login_required
def quick_log(session_id: str) -> Response | str | dict[str, object]:
    """Display the mobile-optimized quick log for a session."""
    db = firestore.client()
    session_data = SessionService.get_session(db, session_id)
    if not session_data:
        flash("Session not found", "danger")
        return redirect(url_for(".view_groups"))

    # Fetch player details for the pool
    players = []
    player_ids = session_data.get("playerIds", [])
    if player_ids:
        player_refs = [db.collection("users").document(pid) for pid in player_ids]
        player_docs = {doc.id: doc for doc in db.get_all(player_refs)}
        for pid in player_ids:
            player_doc = player_docs.get(pid)
            if player_doc and player_doc.exists:
                p_data = player_doc.to_dict() or {}
                p_data["id"] = player_doc.id
                players.append(p_data)

    group_name = "Group"
    group_doc = db.collection("groups").document(session_data["groupId"]).get()
    if group_doc.exists:
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
def view_session(session_id: str) -> Response | str | dict[str, object]:
    """Display session summary and matches."""
    db = firestore.client()
    session_data = SessionService.get_session(db, session_id)
    if not session_data:
        flash("Session not found", "danger")
        return redirect(url_for(".view_groups"))

    # Fetch matches
    match_ids = session_data.get("matchIds", [])
    matches = []
    if match_ids:
        match_refs = [db.collection("matches").document(mid) for mid in match_ids]
        match_docs = {doc.id: doc for doc in db.get_all(match_refs)}
        for mid in match_ids:
            match_doc = match_docs.get(mid)
            if match_doc and match_doc.exists:
                m_data = match_doc.to_dict() or {}
                m_data["id"] = match_doc.id
                matches.append(m_data)

    # Fetch player details for the pool
    players = {}
    player_ids = session_data.get("playerIds", [])
    if player_ids:
        player_refs = [db.collection("users").document(pid) for pid in player_ids]
        for player_doc in db.get_all(player_refs):
            if player_doc.exists:
                p_data = player_doc.to_dict() or {}
                p_data["id"] = player_doc.id
                players[player_doc.id] = p_data

    group_name = "Group"
    group_doc = db.collection("groups").document(session_data["groupId"]).get()
    if group_doc.exists:
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
def verify_session(session_id: str) -> Response | str | dict[str, object]:
    """Trigger batch verification for a session."""
    db = firestore.client()
    success = SessionService.verify_session(db, session_id, g.user.uid)
    if success:
        flash("Session verified!", "success")
    else:
        flash("Failed to verify session. You may not be a participant.", "danger")

    return redirect(url_for(".view_session", session_id=session_id))
