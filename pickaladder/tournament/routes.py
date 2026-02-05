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
        tournament_data["date_display"] = raw_date.to_datetime().strftime("%b %d, %Y")

    match_type = tournament_data.get("matchType", "singles")
    status = tournament_data.get("status", "Active")

    # Resolve Participant Data
    participants = []
    participant_objs = tournament_data.get("participants", [])
    if participant_objs:
        user_refs = [
            (
                obj["userRef"]
                if "userRef" in obj
                else db.collection("users").document(obj["user_id"])
            )
            for obj in participant_objs
            if "userRef" in obj or "user_id" in obj
        ]
        user_docs = db.get_all(user_refs)
        users_map = {
            doc.id: {**doc.to_dict(), "id": doc.id} for doc in user_docs if doc.exists
        }

        for obj in participant_objs:
            uid = obj["userRef"].id if "userRef" in obj else obj.get("user_id")
            if uid and uid in users_map:
                u_data = users_map[uid]
                participants.append(
                    {
                        "user": u_data,
                        "status": obj.get("status", "pending"),
                        "display_name": smart_display_name(u_data),
                        "team_name": obj.get("team_name"),
                    }
                )

    standings = get_tournament_standings(db, tournament_id, match_type)
    podium = standings[:3] if status == "Completed" else []

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
    participant_ids = {
        obj["userRef"].id if "userRef" in obj else obj.get("user_id")
        for obj in participant_objs
    }

    invitable_users = [
        u
        for uid, u in invitable_map.items()
        if uid != current_uid and uid not in participant_ids
    ]
    invitable_users.sort(key=lambda x: smart_display_name(x).lower())

    invite_form = InvitePlayerForm()
    invite_form.user_id.choices = [
        (u["id"], smart_display_name(u)) for u in invitable_users
    ]

    # Ownership check for UI
    is_owner = tournament_data.get("organizer_id") == g.user["uid"] or (
        tournament_data.get("ownerRef")
        and tournament_data["ownerRef"].id == g.user["uid"]
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
    """Edit tournament details."""
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

    tournament_data["id"] = tournament_id

    # Auth check
    is_owner = tournament_data.get("organizer_id") == g.user["uid"] or (
        tournament_data.get("ownerRef")
        and tournament_data["ownerRef"].id == g.user["uid"]
    )
    if not is_owner:
        flash("Unauthorized.", "danger")
        return redirect(url_for(".view_tournament", tournament_id=tournament_id))

    form = TournamentForm()
    if form.validate_on_submit():
        # Check if tournament has started (has matches)
        matches_started = (
            db.collection("matches")
            .where(filter=firestore.FieldFilter("tournamentId", "==", tournament_id))
            .limit(1)
            .stream()
        )
        has_matches = any(matches_started)

        update_data = {
            "name": form.name.data,
            "date": datetime.datetime.combine(form.date.data, datetime.time.min),
            "location": form.location.data,
        }

        # Only allow changing matchType if no matches have been played
        if not has_matches:
            update_data["matchType"] = form.match_type.data
        elif form.match_type.data != tournament_data.get("matchType"):
            flash(
                "Cannot change match type once matches have been recorded.", "warning"
            )

        tournament_ref.update(update_data)
        flash("Tournament updated successfully.", "success")
        return redirect(url_for(".view_tournament", tournament_id=tournament_id))

    elif request.method == "GET":
        form.name.data = tournament_data.get("name")
        form.location.data = tournament_data.get("location")
        form.match_type.data = tournament_data.get("matchType")
        raw_date = tournament_data.get("date")
        if hasattr(raw_date, "to_datetime"):
            form.date.data = raw_date.to_datetime().date()

    return render_template(
        "tournament/edit.html", form=form, tournament=tournament_data
    )


@bp.route("/<string:tournament_id>/invite", methods=["POST"])
@login_required
def invite_player(tournament_id: str) -> Any:
    """Invite a player to a tournament."""
    db = firestore.client()
    tournament_ref = db.collection("tournaments").document(tournament_id)
    tournament_doc = tournament_ref.get()

    if not tournament_doc.exists:
        flash("Tournament not found.", "danger")
        return redirect(url_for(".list_tournaments"))

    tournament_data = tournament_doc.to_dict()
    if not tournament_data:
        flash("Tournament not found.", "danger")
        return redirect(url_for(".list_tournaments"))

    is_owner = tournament_data.get("organizer_id") == g.user["uid"] or (
        tournament_data.get("ownerRef")
        and tournament_data["ownerRef"].id == g.user["uid"]
    )
    if not is_owner:
        flash("Only the owner can invite players.", "danger")
        return redirect(url_for(".view_tournament", tournament_id=tournament_id))

    form = InvitePlayerForm()
    # Dynamically set choices to allow the submitted user_id to pass validation
    submitted_uid = request.form.get("user_id")
    if submitted_uid:
        form.user_id.choices = [(submitted_uid, "")]

    if form.validate_on_submit():
        invited_user_id = form.user_id.data
        invited_user_ref = db.collection("users").document(invited_user_id)

        try:
            tournament_ref.update(
                {
                    "participants": firestore.ArrayUnion(
                        [
                            {
                                "userRef": invited_user_ref,
                                "status": "pending",
                                "team_name": None,
                            }
                        ]
                    ),
                    "participant_ids": firestore.ArrayUnion([invited_user_id]),
                }
            )
            flash("Player invited successfully.", "success")
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")

    return redirect(url_for(".view_tournament", tournament_id=tournament_id))


@bp.route("/<string:tournament_id>/accept", methods=["POST"])
@login_required
def accept_invite(tournament_id: str) -> Any:
    """Accept an invite to a tournament using a transaction."""
    db = firestore.client()
    tournament_ref = db.collection("tournaments").document(tournament_id)

    @firestore.transactional
    def update_in_transaction(transaction, t_ref):
        snapshot = t_ref.get(transaction=transaction)
        if not snapshot.exists:
            return False

        participants = snapshot.get("participants")
        updated = False
        for p in participants:
            p_uid = p["userRef"].id if "userRef" in p else p.get("user_id")
            if p_uid == g.user["uid"] and p["status"] == "pending":
                p["status"] = "accepted"
                updated = True
                break

        if updated:
            transaction.update(t_ref, {"participants": participants})
            return True
        return False

    success = update_in_transaction(db.transaction(), tournament_ref)

    if success:
        flash("You have accepted the tournament invite!", "success")
    else:
        flash("Invite not found or already accepted.", "warning")

    return redirect(request.referrer or url_for("user.dashboard"))


@bp.route("/<string:tournament_id>/decline", methods=["POST"])
@login_required
def decline_invite(tournament_id: str) -> Any:
    """Decline an invite to a tournament using a transaction."""
    db = firestore.client()
    tournament_ref = db.collection("tournaments").document(tournament_id)

    @firestore.transactional
    def update_in_transaction(transaction, t_ref):
        snapshot = t_ref.get(transaction=transaction)
        if not snapshot.exists:
            return False

        participants = snapshot.get("participants")
        participant_ids = snapshot.get("participant_ids")

        new_participants = [
            p
            for p in participants
            if not (
                (p["userRef"].id if "userRef" in p else p.get("user_id"))
                == g.user["uid"]
                and p["status"] == "pending"
            )
        ]

        if len(new_participants) < len(participants):
            new_participant_ids = [
                uid for uid in participant_ids if uid != g.user["uid"]
            ]
            transaction.update(
                t_ref,
                {
                    "participants": new_participants,
                    "participant_ids": new_participant_ids,
                },
            )
            return True
        return False

    success = update_in_transaction(db.transaction(), tournament_ref)

    if success:
        flash("You have declined the tournament invite.", "info")
    else:
        flash("Invite not found.", "warning")

    return redirect(request.referrer or url_for("user.dashboard"))


@bp.route("/<string:tournament_id>/complete", methods=["POST"])
@login_required
def complete_tournament(tournament_id: str) -> Any:
    """Close tournament and send results to all participants."""
    db = firestore.client()
    tournament_ref = db.collection("tournaments").document(tournament_id)
    tournament_doc = tournament_ref.get()

    if not tournament_doc.exists:
        flash("Tournament not found.", "danger")
        return redirect(url_for(".list_tournaments"))

    t_data = tournament_doc.to_dict()
    if t_data.get("ownerRef").id != g.user["uid"]:
        flash("Only the organizer can complete the tournament.", "danger")
        return redirect(url_for(".view_tournament", tournament_id=tournament_id))

    try:
        tournament_ref.update({"status": "Completed"})
        standings = get_tournament_standings(db, tournament_id, t_data.get("matchType"))
        winner_name = standings[0]["name"] if standings else "No one"

        # Notify accepted participants via email
        participants = t_data.get("participants", [])
        for p in participants:
            if p.get("status") == "accepted":
                u_doc = p["userRef"].get()
                if u_doc.exists:
                    user = u_doc.to_dict()
                    if user.get("email"):
                        try:
                            send_email(
                                to=user["email"],
                                subject=f"The results are in for {t_data['name']}!",
                                template="email/tournament_results.html",
                                user=user,
                                tournament=t_data,
                                winner_name=winner_name,
                                standings=standings[:3],
                            )
                        except Exception as e:
                            current_app.logger.error(
                                f"Failed to email {user['email']}: {e}"
                            )

        flash("Tournament completed and results emailed!", "success")
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")

    return redirect(url_for(".view_tournament", tournament_id=tournament_id))


@bp.route("/<string:tournament_id>/join", methods=["POST"])
@login_required
def join_tournament(tournament_id: str) -> Any:
    """Accept tournament invitation (legacy alias)."""
    return accept_invite(tournament_id)
