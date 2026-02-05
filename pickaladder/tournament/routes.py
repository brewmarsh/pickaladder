"""Routes for the tournament blueprint."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, cast

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
from pickaladder.user.utils import smart_display_name
from pickaladder.utils import send_email

from . import bp
from .forms import InvitePlayerForm, TournamentForm
from .utils import (
    get_invitable_users,
    get_tournament_standings,
    resolve_participants,
)

if TYPE_CHECKING:
    from google.cloud.firestore_v1.base_document import DocumentSnapshot
    from google.cloud.firestore_v1.client import Client
    from google.cloud.firestore_v1.transaction import Transaction

from flask import Response


@bp.route("/", methods=["GET"])
@login_required
def list_tournaments() -> str | Response:
    """List all tournaments."""
    db: Client = firestore.client()
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
def create_tournament() -> str | Response:
    """Create a new tournament."""
    form = TournamentForm()
    if form.validate_on_submit():
        db: Client = firestore.client()
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
            return cast(
                Response,
                redirect(
                    url_for(".view_tournament", tournament_id=new_tournament_ref.id)
                ),
            )
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")

    return render_template("create_tournament.html", form=form)


@bp.route("/<string:tournament_id>", methods=["GET", "POST"])
@login_required
def view_tournament(tournament_id: str) -> str | Response:
    """View a single tournament lobby."""
    db: Client = firestore.client()
    tournament_ref = db.collection("tournaments").document(tournament_id)
    tournament_doc = cast("DocumentSnapshot", tournament_ref.get())

    if not tournament_doc.exists:
        flash("Tournament not found.", "danger")
        return cast(Response, redirect(url_for(".list_tournaments")))

    tournament_data = cast(dict[str, Any], tournament_doc.to_dict() or {})
    tournament_data["id"] = tournament_doc.id

    # Format Date
    raw_date = tournament_data.get("date")
    if raw_date and hasattr(raw_date, "to_datetime"):
        tournament_data["date_display"] = raw_date.to_datetime().strftime("%b %d, %Y")

    match_type = tournament_data.get("matchType", "singles")
    status = tournament_data.get("status", "Active")

    # Resolve Participant Data
    participant_objs = tournament_data.get("participants", [])
    participants = resolve_participants(db, participant_objs)

    standings = get_tournament_standings(db, tournament_id, match_type)
    podium = standings[:3] if status == "Completed" else []

    # Handle Invitations
    invite_form = InvitePlayerForm()
    invitable_users = get_invitable_users(db, g.user["uid"], participant_objs)

    invite_form.user_id.choices = [
        (u["id"], smart_display_name(u)) for u in invitable_users
    ]

    # Handle Invite Form Submission from the view page itself
    if invite_form.validate_on_submit() and "user_id" in request.form:
        invited_uid = invite_form.user_id.data
        invited_ref = db.collection("users").document(invited_uid)
        try:
            tournament_ref.update(
                {
                    "participants": firestore.ArrayUnion(
                        [
                            {
                                "userRef": invited_ref,
                                "status": "pending",
                                "team_name": None,
                            }
                        ]
                    ),
                    "participant_ids": firestore.ArrayUnion([invited_uid]),
                }
            )
            flash("Player invited successfully.", "success")
            return cast(
                Response,
                redirect(url_for(".view_tournament", tournament_id=tournament_id)),
            )
        except Exception as e:
            flash(f"Error sending invite: {e}", "danger")

    # Ownership check for UI
    is_owner = tournament_data.get("organizer_id") == g.user["uid"] or (
        tournament_data.get("ownerRef")
        and cast(Any, tournament_data["ownerRef"]).id == g.user["uid"]
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
def edit_tournament(tournament_id: str) -> str | Response:
    """Edit tournament details."""
    db: Client = firestore.client()
    tournament_ref = db.collection("tournaments").document(tournament_id)
    tournament_doc = cast("DocumentSnapshot", tournament_ref.get())

    if not tournament_doc.exists:
        flash("Tournament not found.", "danger")
        return cast(Response, redirect(url_for(".list_tournaments")))

    tournament_data = cast(dict[str, Any], tournament_doc.to_dict() or {})
    tournament_data["id"] = tournament_id

    # Auth check
    is_owner = tournament_data.get("organizer_id") == g.user["uid"] or (
        tournament_data.get("ownerRef")
        and cast(Any, tournament_data["ownerRef"]).id == g.user["uid"]
    )
    if not is_owner:
        flash("Unauthorized.", "danger")
        return cast(
            Response, redirect(url_for(".view_tournament", tournament_id=tournament_id))
        )

    form = TournamentForm()
    if form.validate_on_submit():
        date_val = form.date.data
        if date_val is None:
            flash("Date is required.", "danger")
            return render_template(
                "tournament/edit.html", form=form, tournament=tournament_data
            )

        update_data = {
            "name": form.name.data,
            "date": datetime.datetime.combine(date_val, datetime.time.min),
            "location": form.location.data,
            "matchType": form.match_type.data,
        }
        tournament_ref.update(update_data)
        flash("Updated!", "success")
        return cast(
            Response, redirect(url_for(".view_tournament", tournament_id=tournament_id))
        )

    elif request.method == "GET":
        form.name.data = tournament_data.get("name")
        form.location.data = tournament_data.get("location")
        form.match_type.data = tournament_data.get("matchType")
        raw_date = tournament_data.get("date")
        if raw_date and hasattr(raw_date, "to_datetime"):
            form.date.data = raw_date.to_datetime().date()

    return render_template(
        "tournament/edit.html", form=form, tournament=tournament_data
    )


@bp.route("/<string:tournament_id>/invite", methods=["GET", "POST"])
@login_required
def invite_player(tournament_id: str) -> Response:
    """Invites a player (Endpoint used by the form)."""
    if request.method == "GET":
        return cast(
            Response, redirect(url_for(".view_tournament", tournament_id=tournament_id))
        )

    db: Client = firestore.client()
    user_id = request.form.get("user_id")
    if not user_id:
        flash("No player selected.", "danger")
        return cast(
            Response, redirect(url_for(".view_tournament", tournament_id=tournament_id))
        )

    invited_ref = db.collection("users").document(user_id)
    tournament_ref = db.collection("tournaments").document(tournament_id)

    tournament_ref.update(
        {
            "participants": firestore.ArrayUnion(
                [{"userRef": invited_ref, "status": "pending", "team_name": None}]
            ),
            "participant_ids": firestore.ArrayUnion([user_id]),
        }
    )
    flash("Invite sent!", "success")
    return cast(
        Response, redirect(url_for(".view_tournament", tournament_id=tournament_id))
    )


@bp.route("/<string:tournament_id>/accept", methods=["POST"])
@login_required
def accept_invite(tournament_id: str) -> Response:
    """Accept an invite to a tournament using a transaction."""
    db: Client = firestore.client()
    tournament_ref = db.collection("tournaments").document(tournament_id)

    @firestore.transactional
    def update_in_transaction(transaction: Transaction, t_ref: Any) -> bool:
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

    return cast(Response, redirect(request.referrer or url_for("user.dashboard")))


@bp.route("/<string:tournament_id>/decline", methods=["POST"])
@login_required
def decline_invite(tournament_id: str) -> Response:
    """Decline an invite to a tournament using a transaction."""
    db: Client = firestore.client()
    tournament_ref = db.collection("tournaments").document(tournament_id)

    @firestore.transactional
    def update_in_transaction(transaction: Transaction, t_ref: Any) -> bool:
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

    return cast(Response, redirect(request.referrer or url_for("user.dashboard")))


@bp.route("/<string:tournament_id>/complete", methods=["POST"])
@login_required
def complete_tournament(tournament_id: str) -> Response:
    """Close tournament and send results to all participants."""
    db: Client = firestore.client()
    tournament_ref = db.collection("tournaments").document(tournament_id)
    tournament_doc = cast("DocumentSnapshot", tournament_ref.get())

    if not tournament_doc.exists:
        flash("Tournament not found.", "danger")
        return cast(Response, redirect(url_for(".list_tournaments")))

    t_data = cast(dict[str, Any], tournament_doc.to_dict() or {})
    if cast(Any, t_data.get("ownerRef")).id != g.user["uid"]:
        flash("Only the organizer can complete the tournament.", "danger")
        return cast(
            Response, redirect(url_for(".view_tournament", tournament_id=tournament_id))
        )

    try:
        tournament_ref.update({"status": "Completed"})
        match_type = str(t_data.get("matchType", "singles"))
        standings = get_tournament_standings(db, tournament_id, match_type)
        winner_name = standings[0]["name"] if standings else "No one"

        # Notify accepted participants via email
        participants = cast(list[dict[str, Any]], t_data.get("participants", []))
        for p in participants:
            if p.get("status") == "accepted":
                u_doc = cast("DocumentSnapshot", p["userRef"].get())
                user_data = u_doc.to_dict()
                if u_doc.exists and user_data and user_data.get("email"):
                    recipient_email = str(user_data["email"])
                    t_name = str(t_data.get("name", "Tournament"))
                    try:
                        send_email(
                            to=recipient_email,
                            subject=f"The results are in for {t_name}!",
                            template="email/tournament_results.html",
                            user=user_data,
                            tournament=t_data,
                            winner_name=winner_name,
                            standings=standings[:3],
                        )
                    except Exception as e:
                        current_app.logger.error(
                            f"Failed to email {recipient_email}: {e}"
                        )

        flash("Tournament completed and results emailed!", "success")
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")

    return cast(
        Response, redirect(url_for(".view_tournament", tournament_id=tournament_id))
    )


@bp.route("/<string:tournament_id>/join", methods=["POST"])
@login_required
def join_tournament(tournament_id: str) -> Response:
    """Accept tournament invitation (legacy alias)."""
    return cast(Response, accept_invite(tournament_id))
