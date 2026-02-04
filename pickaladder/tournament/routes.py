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

    # Fetch tournaments where the user is an owner or participant
    # Note: Firestore 'array-contains' might be tricky with objects in arrays.
    # Usually, it's better to store participant IDs in a separate array for querying.
    # But for now, let's fetch all and filter, or just fetch all public ones if
    # they existed. User specifically said: "stores them in a participants array
    # with a 'pending' status" To query efficiently, we might need a separate
    # 'participant_ids' array.

    # For now, let's fetch tournaments where ownerRef is the user
    owned_tournaments = (
        db.collection("tournaments").where("ownerRef", "==", user_ref).stream()
    )

    # And tournaments where user is a participant.
    # Since we store objects in 'participants', we can't use 'array-contains' on the
    # object unless we know the exact object.
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
            # Ensure form.date.data is not None for mypy
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
    """View a single tournament."""
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

    # Handle date conversion for display
    raw_date = tournament_data.get("date")
    if hasattr(raw_date, "to_datetime"):
        tournament_data["date"] = raw_date.to_datetime().date()
    match_type = tournament_data.get("matchType", "singles")
    status = tournament_data.get("status", "Active")

    # Fetch participant data
    participants = []
    participant_objs = tournament_data.get("participants", [])
    if participant_objs:
        user_refs = [obj["userRef"] for obj in participant_objs]
        user_docs = db.get_all(user_refs)
        users_map = {
            doc.id: {**doc.to_dict(), "id": doc.id} for doc in user_docs if doc.exists
        }

        for obj in participant_objs:
            user_id = obj["userRef"].id
            if user_id in users_map:
                user_data = users_map[user_id]
                participants.append(
                    {
                        "user": user_data,
                        "status": obj["status"],
                        "display_name": smart_display_name(user_data),
                    }
                )

    # Calculate Standings
    standings = get_tournament_standings(db, tournament_id, match_type)
    podium = standings[:3] if status == "Completed" else []

    # Invite form
    invite_form = InvitePlayerForm()

    # Source 1: Friends
    friends = UserService.get_user_friends(db, g.user["uid"])

    # Source 2: Groups
    user_ref = db.collection("users").document(g.user["uid"])
    groups_query = (
        db.collection("groups")
        .where(filter=firestore.FieldFilter("members", "array_contains", user_ref))
        .stream()
    )

    group_member_refs = set()
    for group_doc in groups_query:
        group_data = group_doc.to_dict()
        if group_data and "members" in group_data:
            for member_ref in group_data["members"]:
                group_member_refs.add(member_ref)

    group_members = []
    if group_member_refs:
        group_members_docs = db.get_all(list(group_member_refs))
        for doc in group_members_docs:
            if doc.exists:
                data = doc.to_dict()
                if data:
                    group_members.append({"id": doc.id, **data})

    # Deduplicate & Filter
    invitable_map = {u["id"]: u for u in friends}
    for u in group_members:
        invitable_map[u["id"]] = u

    current_uid = g.user["uid"]
    participant_ids = {obj["userRef"].id for obj in participant_objs}

    invitable_users = [
        u
        for uid, u in invitable_map.items()
        if uid != current_uid and uid not in participant_ids
    ]

    invite_form.player.choices = [
        (u["id"], smart_display_name(u)) for u in invitable_users
    ]

    if invite_form.validate_on_submit() and "player" in request.form:
        invited_user_id = invite_form.player.data
        invited_user_ref = db.collection("users").document(invited_user_id)

        try:
            tournament_ref.update(
                {
                    "participants": firestore.ArrayUnion(
                        [{"userRef": invited_user_ref, "status": "pending"}]
                    ),
                    "participant_ids": firestore.ArrayUnion([invited_user_id]),
                }
            )
            flash("Player invited successfully.", "success")
            return redirect(url_for(".view_tournament", tournament_id=tournament_id))
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")

    owner_ref = tournament_data.get("ownerRef")
    is_owner = tournament_data.get("organizer_id") == g.user["uid"] or (
        owner_ref and owner_ref.id == g.user["uid"]
    )

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
    """Edit an existing tournament."""
    db = firestore.client()
    tournament_ref = db.collection("tournaments").document(tournament_id)
    tournament_doc = tournament_ref.get()

    if not tournament_doc.exists:
        flash("Tournament not found.", "danger")
        return redirect(url_for(".list_tournaments"))

    tournament_data = tournament_doc.to_dict()
    if tournament_data is None:
        flash("Tournament data is empty.", "danger")
        return redirect(url_for(".list_tournaments"))
    tournament_data["id"] = tournament_id

    # Authorization
    organizer_id = tournament_data.get("organizer_id")
    owner_ref = tournament_data.get("ownerRef")
    is_authorized = organizer_id == g.user["uid"] or (
        owner_ref and owner_ref.id == g.user["uid"]
    )

    if not is_authorized:
        flash("You are not authorized to edit this tournament.", "danger")
        return redirect(url_for(".view_tournament", tournament_id=tournament_id))

    # Check if ongoing
    matches_query = (
        db.collection("matches")
        .where(filter=firestore.FieldFilter("tournamentId", "==", tournament_id))
        .limit(1)
        .stream()
    )
    is_ongoing = any(matches_query)

    form = TournamentForm()

    if form.validate_on_submit():
        # Ensure form.date.data is not None for mypy
        date_val = form.date.data
        if date_val is None:
            flash("Date is required.", "danger")
            return render_template(
                "tournament/edit.html",
                form=form,
                tournament=tournament_data,
                is_ongoing=is_ongoing,
            )

        update_data = {
            "name": form.name.data,
            "date": datetime.datetime.combine(date_val, datetime.time.min),
            "location": form.location.data,
        }
        if not is_ongoing:
            update_data["matchType"] = form.match_type.data

        try:
            tournament_ref.update(update_data)
            flash("Tournament updated successfully.", "success")
            return redirect(url_for(".view_tournament", tournament_id=tournament_id))
        except Exception as e:
            flash(f"An error occurred: {e}", "danger")
    elif request.method == "GET":
        form.name.data = tournament_data.get("name")
        form.location.data = tournament_data.get("location")
        form.match_type.data = tournament_data.get("matchType")

        # Handle date conversion
        raw_date = tournament_data.get("date")
        if isinstance(raw_date, datetime.datetime):
            form.date.data = raw_date.date()
        elif hasattr(raw_date, "to_datetime"):  # Firestore Timestamp
            form.date.data = raw_date.to_datetime().date()
        elif isinstance(raw_date, str):
            try:
                form.date.data = datetime.datetime.strptime(raw_date, "%Y-%m-%d").date()
            except ValueError:
                pass

    return render_template(
        "tournament/edit.html",
        form=form,
        tournament=tournament_data,
        is_ongoing=is_ongoing,
    )


@bp.route("/<string:tournament_id>/complete", methods=["POST"])
@login_required
def complete_tournament(tournament_id: str) -> Any:
    """Mark a tournament as completed and notify participants."""
    db = firestore.client()
    tournament_ref = db.collection("tournaments").document(tournament_id)
    tournament_doc = tournament_ref.get()

    if not tournament_doc.exists:
        flash("Tournament not found.", "danger")
        return redirect(url_for(".list_tournaments"))

    tournament_data = tournament_doc.to_dict()
    if tournament_data.get("ownerRef").id != g.user["uid"]:
        flash("Only the owner can complete the tournament.", "danger")
        return redirect(url_for(".view_tournament", tournament_id=tournament_id))

    try:
        tournament_ref.update({"status": "Completed"})

        # Calculate final standings for the email
        match_type = tournament_data.get("matchType", "singles")
        standings = get_tournament_standings(db, tournament_id, match_type)
        winner_name = standings[0]["name"] if standings else "No one"

        # Send emails to all participants
        participants = tournament_data.get("participants", [])
        user_refs = [p["userRef"] for p in participants if p["status"] == "accepted"]
        if user_refs:
            user_docs = db.get_all(user_refs)
            for user_doc in user_docs:
                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    email = user_data.get("email")
                    if email:
                        try:
                            subject = (
                                f"The results are in for {tournament_data['name']}!"
                            )
                            send_email(
                                to=email,
                                subject=subject,
                                template="email/tournament_results.html",
                                user=user_data,
                                tournament=tournament_data,
                                winner_name=winner_name,
                                standings=standings[:3],
                            )
                        except Exception as e:
                            msg = (
                                f"Failed to send tournament results email "
                                f"to {email}: {e}"
                            )
                            current_app.logger.error(msg)

        flash("Tournament completed and results sent!", "success")
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")

    return redirect(url_for(".view_tournament", tournament_id=tournament_id))


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
