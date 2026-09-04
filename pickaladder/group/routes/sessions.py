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

    # ⚡ Bolt Optimization: Batch independent document reads into a single network request
    # What: Fetch player documents and the group document concurrently using a single db.get_all()
    # Why: Reduces N+1 latency bottlenecks by avoiding sequential database I/O for different collections
    # Impact: Reduces database request roundtrips from 2 to 1, improving page load speed
    player_ids = session_data.get("playerIds", [])
    player_refs = [db.collection("users").document(pid) for pid in player_ids]
    group_ref = db.collection("groups").document(session_data["groupId"])

    all_refs = player_refs + [group_ref]
    all_docs = {doc.reference.path: doc for doc in db.get_all(all_refs) if doc.exists}

    players = []
    for pid in player_ids:
        player_path = f"users/{pid}"
        if player_path in all_docs:
            player_doc = all_docs[player_path]
            p_data = player_doc.to_dict() or {}
            p_data["id"] = player_doc.id
            players.append(p_data)

    group_name = "Group"
    group_path = f"groups/{session_data['groupId']}"
    if group_path in all_docs:
        group_doc = all_docs[group_path]
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

    # ⚡ Bolt Optimization: Batch independent document reads into a single network request
    # What: Fetch match documents, player documents, and the group document concurrently using a single db.get_all()
    # Why: Reduces N+1 latency bottlenecks by avoiding sequential database I/O for different collections
    # Impact: Reduces database request roundtrips from 3 to 1, improving page load speed
    match_ids = session_data.get("matchIds", [])
    player_ids = session_data.get("playerIds", [])

    match_refs = [db.collection("matches").document(mid) for mid in match_ids]
    player_refs = [db.collection("users").document(pid) for pid in player_ids]
    group_ref = db.collection("groups").document(session_data["groupId"])

    all_refs = match_refs + player_refs + [group_ref]
    all_docs = {doc.reference.path: doc for doc in db.get_all(all_refs) if doc.exists}

    # Process matches
    matches = []
    for mid in match_ids:
        match_path = f"matches/{mid}"
        if match_path in all_docs:
            match_doc = all_docs[match_path]
            m_data = match_doc.to_dict() or {}
            m_data["id"] = match_doc.id
            matches.append(m_data)

    # Process players
    players = {}
    for pid in player_ids:
        player_path = f"users/{pid}"
        if player_path in all_docs:
            player_doc = all_docs[player_path]
            p_data = player_doc.to_dict() or {}
            p_data["id"] = player_doc.id
            players[player_doc.id] = p_data

    # Process group
    group_name = "Group"
    group_path = f"groups/{session_data['groupId']}"
    if group_path in all_docs:
        group_doc = all_docs[group_path]
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
