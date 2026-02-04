"""Routes for the tournament blueprint."""

from __future__ import annotations

from typing import Any

from firebase_admin import firestore
from flask import (
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

from pickaladder.auth.decorators import login_required
from pickaladder.user.utils import UserService, smart_display_name

from . import bp
from .forms import InvitePlayerForm, TournamentForm


@bp.route("/", methods=["GET"])
@login_required
def list_tournaments() -> Any:
    """List all tournaments."""
    db = firestore.client()
    user_ref = db.collection("users").document(g.user["uid"])

    # Fetch tournaments where the user is an owner or participant
    # Note: Firestore 'array-contains' might be tricky with objects in arrays.
    # Usually, it's better to store participant IDs in a separate array for querying.
    # But for now, let's fetch all and filter, or just fetch all public ones if they existed.
    # User specifically said: "stores them in a participants array with a 'pending' status"
    # To query efficiently, we might need a separate 'participant_ids' array.

    # For now, let's fetch tournaments where ownerRef is the user
    owned_tournaments = (
        db.collection("tournaments")
        .where("ownerRef", "==", user_ref)
        .stream()
    )

    # And tournaments where user is a participant.
    # Since we store objects in 'participants', we can't use 'array-contains' on the object
    # unless we know the exact object.
    # Let's also maintain a 'participant_ids' array for easier querying.
    participating_tournaments = (
        db.collection("tournaments")
        .where("participant_ids", "array_contains", g.user["uid"])
        .stream()
    )

    tournaments = []
    seen_ids = set()

    for doc in owned_tournaments:
        data = doc.to_dict()
        data["id"] = doc.id
        tournaments.append(data)
        seen_ids.add(doc.id)

    for doc in participating_tournaments:
        if doc.id not in seen_ids:
            data = doc.to_dict()
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
            tournament_data = {
                "name": form.name.data,
                "date": str(form.date.data),
                "location": form.location.data,
                "matchType": form.match_type.data,
                "ownerRef": user_ref,
                "participants": [
                    {"userRef": user_ref, "status": "accepted"}
                ],
                "participant_ids": [g.user["uid"]],
                "createdAt": firestore.SERVER_TIMESTAMP,
            }
            _, new_tournament_ref = db.collection("tournaments").add(tournament_data)
            flash("Tournament created successfully.", "success")
            return redirect(url_for(".view_tournament", tournament_id=new_tournament_ref.id))
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")

    return render_template("create_tournament.html", form=form)


@bp.route("/<string:tournament_id>", methods=["GET", "POST"])
@login_required
def view_tournament(tournament_id: str) -> Any:
    """View a single tournament."""
    db = firestore.client()
    tournament_ref = db.collection("tournaments").document(tournament_id)
    tournament_doc = tournament_ref.get()

    if not tournament_doc.exists:
        flash("Tournament not found.", "danger")
        return redirect(url_for(".list_tournaments"))

    tournament_data = tournament_doc.to_dict()
    tournament_data["id"] = tournament_doc.id

    # Fetch participant data
    participants = []
    participant_objs = tournament_data.get("participants", [])
    if participant_objs:
        user_refs = [obj["userRef"] for obj in participant_objs]
        user_docs = db.get_all(user_refs)
        users_map = {doc.id: {**doc.to_dict(), "id": doc.id} for doc in user_docs if doc.exists}

        for obj in participant_objs:
            user_id = obj["userRef"].id
            if user_id in users_map:
                user_data = users_map[user_id]
                participants.append({
                    "user": user_data,
                    "status": obj["status"],
                    "display_name": smart_display_name(user_data)
                })

    # Invite form
    invite_form = InvitePlayerForm()
    # Populate choices with friends not in the tournament
    user_ref = db.collection("users").document(g.user["uid"])
    friends = UserService.get_user_friends(db, g.user["uid"])
    participant_ids = {obj["userRef"].id for obj in participant_objs}

    eligible_friends = [f for f in friends if f["id"] not in participant_ids]
    invite_form.player.choices = [(f["id"], f.get("name") or f["id"]) for f in eligible_friends]

    if invite_form.validate_on_submit() and "player" in request.form:
        invited_user_id = invite_form.player.data
        invited_user_ref = db.collection("users").document(invited_user_id)

        try:
            tournament_ref.update({
                "participants": firestore.ArrayUnion([{"userRef": invited_user_ref, "status": "pending"}]),
                "participant_ids": firestore.ArrayUnion([invited_user_id])
            })
            flash("Player invited successfully.", "success")
            return redirect(url_for(".view_tournament", tournament_id=tournament_id))
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")

    return render_template(
        "tournament.html",
        tournament=tournament_data,
        participants=participants,
        invite_form=invite_form,
        is_owner=(tournament_data.get("ownerRef").id == g.user["uid"])
    )


@bp.route("/<string:tournament_id>/join", methods=["POST"])
@login_required
def join_tournament(tournament_id: str) -> Any:
    """Accept an invite to a tournament."""
    db = firestore.client()
    tournament_ref = db.collection("tournaments").document(tournament_id)
    tournament_doc = tournament_ref.get()

    if not tournament_doc.exists:
        flash("Tournament not found.", "danger")
        return redirect(url_for(".list_tournaments"))

    tournament_data = tournament_doc.to_dict()
    participants = tournament_data.get("participants", [])

    updated = False
    for p in participants:
        if p["userRef"].id == g.user["uid"] and p["status"] == "pending":
            p["status"] = "accepted"
            updated = True
            break

    if updated:
        tournament_ref.update({"participants": participants})
        flash("You have joined the tournament!", "success")
    else:
        flash("No pending invitation found.", "warning")

    return redirect(url_for(".view_tournament", tournament_id=tournament_id))
