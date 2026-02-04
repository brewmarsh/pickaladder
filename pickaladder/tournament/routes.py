"""Routes for the tournament blueprint."""

from __future__ import annotations

import datetime
from typing import Any

from firebase_admin import firestore
from flask import (
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

from pickaladder.auth.decorators import login_required
from pickaladder.user.utils import UserService, smart_display_name
from pickaladder.utils import send_email

from . import bp
from .forms import InvitePlayerForm, TournamentForm
from .utils import get_tournament_standings


@bp.route("/", methods=["GET"])
@login_required
def list_tournaments() -> Any:
    """List all tournaments."""
    db = firestore.client()
    user_ref = db.collection("users").document(g.user["uid"])

    # Fetch tournaments where the user is an owner
    owned_tournaments = (
        db.collection("tournaments").where("ownerRef", "==", user_ref).stream()
    )

    # Fetch tournaments where user is a participant via the participant_ids array
    participating_tournaments = (
        db.collection("tournaments")
        .where("participant_ids", "array_contains", g.user["uid"])
        .stream()
    )

    tournaments = []
    seen_ids = set()

    for doc in owned_tournaments:
        data = doc.to_dict()
        if data:
            data["id"] = doc.id
            tournaments.append(data)
            seen_ids.add(doc.id)

    for doc in participating_tournaments:
        if doc.id not in seen_ids:
            data = doc.to_dict()
            if data:
                data["id"] = doc.id
                tournaments.append(data)
                seen_ids.add(doc.id)

    return render_template("tournaments.html", tournaments=tournaments)


@bp.route("/create", methods=["GET", "POST"])
@login_required
def create_tournament() -> Any:
    """Create a new tournament."""
    form = TournamentForm()
    if form.validate_on_submit():
        db = firestore.client()
        user_ref = db.collection("users").document(g.user["uid"])
        try:
            date_val = form.date.data
            if date_val is None:
                raise ValueError("Date is required")

            tournament_data = {
                "name": form.name.data,
                "date": datetime.datetime.combine(date_val, datetime.time.min),
                "location": form.location.data,
                "matchType": form.match_type.data,
                "ownerRef": user_ref,
                "organizer_id": g.user["uid"],
                "status": "Active",
                "participants": [{"userRef": user_ref, "status": "accepted"}],
                "participant_ids": [g.user["uid"]],
                "createdAt": firestore.SERVER_TIMESTAMP,
            }
            _, new_tournament_ref = db.collection("tournaments").add(tournament_data)
            flash("Tournament created successfully.", "success")
            return redirect(
                url_for(".view_tournament", tournament_id=new_tournament_ref.id)
            )
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")

    return render_template("create_tournament.html", form=form)


@bp.route("/<string:tournament_id>", methods=["GET", "POST"])
@login_required
def view_tournament(tournament_id: str) -> Any:
    """View a single tournament lobby."""
    db = firestore.client()
    tournament_ref = db.collection("tournaments").document(tournament_id)
    tournament_doc = tournament_ref.get()

    if not tournament_doc.exists:
        flash("Tournament not found.", "danger")
        return redirect(url_for(".list_tournaments"))

    tournament_data = tournament_doc.to_dict()
    if tournament_data is None:
        flash("Tournament not found.", "danger")
        return redirect(url_for(".list_tournaments"))
    
    tournament_data["id"] = tournament_doc.id

    # Format Date
    raw_date = tournament_data.get("date")
    if hasattr(raw_date, "to_datetime"):
        tournament_data["date_display"] = raw_date.to_datetime().strftime('%b %d, %Y')
    
    match_type = tournament_data.get("matchType", "singles")
    status = tournament_data.get("status", "Active")

    # Resolve Participant Data
    participants = []
    participant_objs = tournament_data.get("participants", [])
    if participant_objs:
        user_refs = [
            obj["userRef"] if "userRef" in obj else db.collection("users").document(obj["user_id"])
            for obj in participant_objs
            if "userRef" in obj or "user_id" in obj
        ]
        user_docs = db.get_all(user_refs)
        users_map = {doc.id: {**doc.to_dict(), "id": doc.id} for doc in user_docs if doc.exists}

        for obj in participant_objs:
            uid = obj["userRef"].id if "userRef" in obj else obj.get("user_id")
            if uid and uid in users_map:
                u_data = users_map[uid]
                participants.append({
                    "user": u_data,
                    "status": obj.get("status", "pending"),
                    "display_name": smart_display_name(u_data),
                    "team_name": obj.get("team_name")
                })

    standings = get_tournament_standings(db, tournament_id, match_type)
    podium = standings[:3] if status == "Completed" else []

    # Handle Invitations
    invite_form = InvitePlayerForm()
    friends = UserService.get_user_friends(db, g.user["uid"])
    
    # Filter friends not already in tournament
    current_participant_ids = {
        obj["userRef"].id if "userRef" in obj else obj.get("user_id")
        for obj in participant_objs
    }
    invitable_users = [f for f in friends if f["id"] not in current_participant_ids]
    invite_form.user_id.choices = [(u["id"], smart_display_name(u)) for u in invitable_users]

    # Process Invitation Post (Accepting changes from implementation-tournament-editing)
    if invite_form.validate_on_submit() and "user_id" in request.form:
        invited_uid = invite_form.user_id.data
        invited_ref = db.collection("users").document(invited_uid)
        try:
            tournament_ref.update({
                "participants": firestore.ArrayUnion([{"userRef": invited_ref, "status": "pending", "team_name": None}]),
                "participant_ids": firestore.ArrayUnion([invited_uid]),
            })
            flash("Player invited successfully.", "success")
            return redirect(url_for(".view_tournament", tournament_id=tournament_id))
        except Exception as e:
            flash(f"Error sending invite: {e}", "danger")

    # Ownership check for UI
    is_owner = tournament_data.get("organizer_id") == g.user["uid"] or \
               (tournament_data.get("ownerRef") and tournament_data["ownerRef"].id == g.user["uid"])

    return render_template(
        "tournament/view.html",
        tournament=tournament_data,
        participants=participants,
        standings=standings,
        podium=podium,
        invite_form=invite_form,
        invitable_users=invitable_users,
        is_owner=is_owner,
    )

@bp.route("/<string:tournament_id>/edit", methods=["GET", "POST"])
@login_required
def edit_tournament(tournament_id: str) -> Any:
    """Edit tournament details."""
    db = firestore.client()
    tournament_ref = db.collection("tournaments").document(tournament_id)
    tournament_doc = tournament_ref.get()

    if not tournament_doc.exists:
        flash("Tournament not found.", "danger")
        return redirect(url_for(".list_tournaments"))

    tournament_data = tournament_doc.to_dict()
    tournament_data["id"] = tournament_id

    # Auth check
    is_owner = tournament_data.get("organizer_id") == g.user["uid"] or \
               (tournament_data.get("ownerRef") and tournament_data["ownerRef"].id == g.user["uid"])
    if not is_owner:
        flash("Unauthorized.", "danger")
        return redirect(url_for(".view_tournament", tournament_id=tournament_id))

    form = TournamentForm()
    if form.validate_on_submit():
        update_data = {
            "name": form.name.data,
            "date": datetime.datetime.combine(form.date.data, datetime.time.min),
            "location": form.location.data,
            "matchType": form.match_type.data,
        }
        tournament_ref.update(update_data)
        flash("Updated!", "success")
        return redirect(url_for(".view_tournament", tournament_id=tournament_id))
    
    elif request.method == "GET":
        form.name.data = tournament_data.get("name")
        form.location.data = tournament_data.get("location")
        form.match_type.data = tournament_data.get("matchType")
        raw_date = tournament_data.get("date")
        if hasattr(raw_date, "to_datetime"):
            form.date.data = raw_date.to_datetime().date()

    return render_template("tournament/edit.html", form=form, tournament=tournament_data)

@bp.route("/<string:tournament_id>/invite", methods=["POST"])
@login_required
def invite_player(tournament_id: str) -> Any:
    """Invites a player (Endpoint used by the form)."""
    db = firestore.client()
    user_id = request.form.get("user_id")
    if not user_id:
        flash("No player selected.", "danger")
        return redirect(url_for(".view_tournament", tournament_id=tournament_id))

    invited_ref = db.collection("users").document(user_id)
    tournament_ref = db.collection("tournaments").document(tournament_id)
    
    tournament_ref.update({
        "participants": firestore.ArrayUnion([{"userRef": invited_ref, "status": "pending", "team_name": None}]),
        "participant_ids": firestore.ArrayUnion([user_id]),
    })
    flash("Invite sent!", "success")
    return redirect(url_for(".view_tournament", tournament_id=tournament_id))

@bp.route("/<string:tournament_id>/complete", methods=["POST"])
@login_required
def complete_tournament(tournament_id: str) -> Any:
    """Close tournament and send results."""
    db = firestore.client()
    tournament_ref = db.collection("tournaments").document(tournament_id)
    tournament_doc = tournament_ref.get()
    t_data = tournament_doc.to_dict()

    tournament_ref.update({"status": "Completed"})
    standings = get_tournament_standings(db, tournament_id, t_data.get("matchType"))
    
    # Notify accepted participants via email
    for p in t_data.get("participants", []):
        if p.get("status") == "accepted":
            u_doc = p["userRef"].get()
            if u_doc.exists:
                user = u_doc.to_dict()
                if user.get("email"):
                    send_email(
                        to=user["email"],
                        subject=f"Results for {t_data['name']}",
                        template="email/tournament_results.html",
                        user=user,
                        tournament=t_data,
                        standings=standings[:3]
                    )

    flash("Tournament completed and results emailed!", "success")
    return redirect(url_for(".view_tournament", tournament_id=tournament_id))

@bp.route("/<string:tournament_id>/join", methods=["POST"])
@login_required
def join_tournament(tournament_id: str) -> Any:
    """Accept tournament invitation."""
    db = firestore.client()
    t_ref = db.collection("tournaments").document(tournament_id)
    t_doc = t_ref.get()
    t_data = t_doc.to_dict()
    
    participants = t_data.get("participants", [])
    for p in participants:
        uid = p["userRef"].id if "userRef" in p else p.get("user_id")
        if uid == g.user["uid"]:
            p["status"] = "accepted"
            break
            
    t_ref.update({"participants": participants})
    flash("Welcome to the tournament!", "success")
    return redirect(url_for(".view_tournament", tournament_id=tournament_id))