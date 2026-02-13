"""Routes for the tournament blueprint."""

from __future__ import annotations

import datetime
from typing import Any

from firebase_admin import firestore  # noqa: F401
from flask import (
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

from pickaladder.auth.decorators import admin_required, login_required
from pickaladder.user.helpers import smart_display_name

from . import bp
from .forms import InvitePlayerForm, TournamentForm
from .services import TournamentGenerator, TournamentService

MIN_PARTICIPANTS_FOR_GENERATION = 2


@bp.route("/", methods=["GET"])
@login_required
def list_tournaments() -> Any:
    """List all tournaments."""
    tournaments = TournamentService.list_tournaments(g.user["uid"])
    return render_template("tournaments.html", tournaments=tournaments)


@bp.route("/create", methods=["GET", "POST"])
@admin_required
def create_tournament() -> Any:
    """Create a new tournament."""
    group_id = request.args.get("group_id")
    if group_id:
        db = firestore.client()
        group_doc = db.collection("groups").document(group_id).get()
        if group_doc.exists:
            from pickaladder.group.services.group_service import GroupService

            if not GroupService.is_group_admin(group_doc.to_dict(), g.user["uid"]):
                flash(
                    "You do not have permission to create a tournament for this group.",
                    "danger",
                )
                return redirect(url_for("group.view_group", group_id=group_id))

    form = TournamentForm()
    if form.validate_on_submit():
        try:
            date_val = form.date.data
            if date_val is None:
                raise ValueError("Date is required")

            data = {
                "name": form.name.data,
                "date": datetime.datetime.combine(date_val, datetime.time.min),
                "location": form.location.data,
                "matchType": form.match_type.data,
                "format": form.format.data,
            }
            tournament_id = TournamentService.create_tournament(data, g.user["uid"])
            flash("Tournament created successfully.", "success")
            return redirect(url_for(".view_tournament", tournament_id=tournament_id))
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")

    return render_template("create_tournament.html", form=form)


@bp.route("/<string:tournament_id>", methods=["GET", "POST"])
@login_required
def view_tournament(tournament_id: str) -> Any:
    """View a single tournament lobby."""
    details = TournamentService.get_tournament_details(tournament_id, g.user["uid"])
    if not details:
        flash("Tournament not found.", "danger")
        return redirect(url_for(".list_tournaments"))

    # Handle Invitations form
    invite_form = InvitePlayerForm()
    invitable_users = details.get("invitable_users", [])
    invite_form.user_id.choices = [
        (u["id"], smart_display_name(u)) for u in invitable_users
    ]

    # Handle Invite Form Submission from the view page itself
    if invite_form.validate_on_submit() and "user_id" in request.form:
        invited_uid = invite_form.user_id.data
        try:
            TournamentService.invite_player(tournament_id, g.user["uid"], invited_uid)
            flash("Player invited successfully.", "success")
            return redirect(url_for(".view_tournament", tournament_id=tournament_id))
        except Exception as e:
            flash(f"Error sending invite: {e}", "danger")

    return render_template(
        "tournament/view.html",
        invite_form=invite_form,
        **details,
    )


@bp.route("/<string:tournament_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_tournament(tournament_id: str) -> Any:
    """Edit tournament details."""
    details = TournamentService.get_tournament_details(tournament_id, g.user["uid"])
    if not details:
        flash("Tournament not found.", "danger")
        return redirect(url_for(".list_tournaments"))

    if not details["is_owner"]:
        flash("Unauthorized.", "danger")
        return redirect(url_for(".view_tournament", tournament_id=tournament_id))

    tournament_data = details["tournament"]
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
            "format": form.format.data,
        }

        try:
            TournamentService.update_tournament(
                tournament_id, g.user["uid"], update_data
            )
            flash("Tournament updated successfully.", "success")
            return redirect(url_for(".view_tournament", tournament_id=tournament_id))
        except ValueError as e:
            flash(str(e), "danger")
        except PermissionError:
            flash("Unauthorized.", "danger")
        except Exception as e:
            flash(f"An error occurred: {e}", "danger")

    elif request.method == "GET":
        form.name.data = tournament_data.get("name")
        form.location.data = tournament_data.get("location")
        form.match_type.data = tournament_data.get("matchType")
        form.format.data = tournament_data.get("format")
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
    form = InvitePlayerForm()
    # Dynamically set choices to allow validation (hacky but standard in this app)
    submitted_uid = request.form.get("user_id")
    if submitted_uid:
        form.user_id.choices = [(submitted_uid, "")]

    if form.validate_on_submit():
        invited_user_id = form.user_id.data
        try:
            TournamentService.invite_player(
                tournament_id, g.user["uid"], invited_user_id
            )
            flash("Player invited successfully.", "success")
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")

    return redirect(url_for(".view_tournament", tournament_id=tournament_id))


@bp.route("/<string:tournament_id>/invite_group", methods=["POST"])
@login_required
def invite_group(tournament_id: str) -> Any:
    """Invite an entire group."""
    group_id = request.form.get("group_id")
    if not group_id:
        flash("No group specified.", "warning")
        return redirect(url_for(".view_tournament", tournament_id=tournament_id))

    try:
        count = TournamentService.invite_group(tournament_id, group_id, g.user["uid"])
        flash(f"Success! Invited {count} members.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except PermissionError as e:
        flash(str(e), "danger")
    except Exception as e:
        flash(f"Error: {e}", "danger")

    return redirect(url_for(".view_tournament", tournament_id=tournament_id))


@bp.route("/<string:tournament_id>/accept", methods=["POST"])
@login_required
def accept_invite(tournament_id: str) -> Any:
    """Accept an invite to a tournament."""
    try:
        success = TournamentService.accept_invite(tournament_id, g.user["uid"])
        if success:
            flash("You have accepted the tournament invite!", "success")
        else:
            flash("Invite not found or already accepted.", "warning")
    except Exception as e:
        flash(f"Error: {e}", "danger")

    return redirect(request.referrer or url_for("user.dashboard"))


@bp.route("/<string:tournament_id>/decline", methods=["POST"])
@login_required
def decline_invite(tournament_id: str) -> Any:
    """Decline an invite to a tournament."""
    try:
        success = TournamentService.decline_invite(tournament_id, g.user["uid"])
        if success:
            flash("You have declined the tournament invite.", "info")
        else:
            flash("Invite not found.", "warning")
    except Exception as e:
        flash(f"Error: {e}", "danger")

    return redirect(request.referrer or url_for("user.dashboard"))


@bp.route("/<string:tournament_id>/complete", methods=["POST"])
@login_required
def complete_tournament(tournament_id: str) -> Any:
    """Close tournament and send results."""
    try:
        TournamentService.complete_tournament(tournament_id, g.user["uid"])
        flash("Tournament completed and results emailed!", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except PermissionError as e:
        flash(str(e), "danger")
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")

    return redirect(url_for(".view_tournament", tournament_id=tournament_id))


@bp.route("/<string:tournament_id>/generate", methods=["POST"])
@login_required
def generate_bracket(tournament_id: str) -> Any:
    """Generate the tournament bracket/pairings."""
    if not g.user.get("isAdmin"):
        flash("Only admins can generate brackets.", "danger")
        return redirect(url_for(".view_tournament", tournament_id=tournament_id))

    db = firestore.client()
    t_ref = db.collection("tournaments").document(tournament_id)
    t_doc = t_ref.get()
    if not t_doc.exists:
        flash("Tournament not found.", "danger")
        return redirect(url_for(".list_tournaments"))

    t_data = t_doc.to_dict() or {}
    if t_data.get("format") != "ROUND_ROBIN":
        flash(
            f"Generation for {t_data.get('format')} is not yet implemented.", "warning"
        )
        return redirect(url_for(".view_tournament", tournament_id=tournament_id))

    # Get accepted participants
    participants = t_data.get("participants", [])
    accepted_ids = [
        (p.get("userRef").id if p.get("userRef") else p.get("user_id"))
        for p in participants
        if p.get("status") == "accepted"
    ]

    if len(accepted_ids) < MIN_PARTICIPANTS_FOR_GENERATION:
        flash(
            "At least 2 accepted participants are required to generate a bracket.",
            "warning",
        )
        return redirect(url_for(".view_tournament", tournament_id=tournament_id))

    # Generate pairings
    pairings = TournamentGenerator.generate_round_robin(accepted_ids)

    # Save to matches sub-collection
    matches_sub_ref = t_ref.collection("matches")
    batch = db.batch()
    for match in pairings:
        batch.set(matches_sub_ref.document(), match)

    # Update status
    batch.update(t_ref, {"status": "PUBLISHED"})
    batch.commit()

    flash(f"Round Robin bracket generated with {len(pairings)} matches!", "success")
    return redirect(url_for(".view_tournament", tournament_id=tournament_id))


@bp.route("/<string:tournament_id>/join", methods=["POST"])
@login_required
def join_tournament(tournament_id: str) -> Any:
    """Accept tournament invitation (legacy alias)."""
    return accept_invite(tournament_id)


@bp.route("/<string:tournament_id>/delete", methods=["POST"])
@admin_required
def delete_tournament(tournament_id: str) -> Any:
    """Delete a tournament."""
    try:
        TournamentService.delete_tournament(tournament_id)
        flash("Tournament deleted successfully.", "success")
        return redirect(url_for(".list_tournaments"))
    except Exception as e:
        flash(f"Error deleting tournament: {e}", "danger")
        return redirect(url_for(".view_tournament", tournament_id=tournament_id))
