"""Routes for the tournament blueprint."""

from __future__ import annotations

import datetime
import logging
from typing import Any

from firebase_admin import firestore  # noqa: F401
from flask import (
    flash,
    g,
    jsonify,
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
            date_val = form.start_date.data
            if date_val is None:
                raise ValueError("Date is required")

            data = {
                "name": form.name.data,
                "date": datetime.datetime.combine(date_val, datetime.time.min),
                "location": form.address.data or form.location.data,
                "mode": form.mode.data,
                "matchType": form.mode.data.lower(),
                "venue_name": form.venue_name.data,
                "description": form.description.data,
                "location_data": {
                    "name": form.venue_name.data,
                    "address": form.address.data
                }
            }
            tournament_id = TournamentService.create_tournament(data, g.user["uid"])

            # Handle banner upload if present
            banner_file = request.files.get("banner")
            if banner_file and banner_file.filename:
                banner_url = TournamentService._upload_banner(
                    tournament_id, banner_file
                )
                if banner_url:
                    TournamentService.update_tournament(
                        tournament_id, g.user["uid"], {"banner_url": banner_url}
                    )

            flash("Tournament created successfully.", "success")
            return redirect(url_for(".view_tournament", tournament_id=tournament_id))
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")

    return render_template("tournaments/create_edit.html", form=form, action="Create")


@bp.route("/<string:tournament_id>", methods=["GET", "POST"])
@login_required
def view_tournament(tournament_id: str) -> Any:
    """View a single tournament lobby."""
    details = TournamentService.get_tournament_details(tournament_id, g.user["uid"])
    if not details:
        flash("Tournament not found.", "danger")
        return redirect(url_for(".list_tournaments"))

    # Handle Claim Team partnership if present in URL
    claim_team_id = request.args.get("claim_team")
    claim_team_data = None
    if claim_team_id:
        db = firestore.client()
        t_ref = db.collection("tournaments").document(tournament_id)
        team_doc = t_ref.collection("teams").document(claim_team_id).get()
        if team_doc.exists:
            claim_team_data = team_doc.to_dict()
            claim_team_data["id"] = team_doc.id
            # Fetch P1 name
            p1_doc = db.collection("users").document(claim_team_data["p1_uid"]).get()
            claim_team_data["p1_name"] = (
                smart_display_name(p1_doc.to_dict()) if p1_doc.exists else "Someone"
            )

    details["claim_team_data"] = claim_team_data

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
        date_val = form.start_date.data
        if date_val is None:
            flash("Date is required.", "danger")
            return render_template(
                "tournaments/create_edit.html",
                form=form,
                tournament=tournament_data,
                action="Edit",
            )

        update_data = {
            "name": form.name.data,
            "date": datetime.datetime.combine(date_val, datetime.time.min),
            "location": form.address.data or form.location.data,
            "mode": form.mode.data,
            "matchType": form.mode.data.lower(),
            "venue_name": form.venue_name.data,
            "description": form.description.data,
            "location_data": {
                "name": form.venue_name.data,
                "address": form.address.data
            }
        }

        # Handle banner upload
        banner_file = request.files.get("banner")
        if banner_file and banner_file.filename:
            banner_url = TournamentService._upload_banner(tournament_id, banner_file)
            if banner_url:
                update_data["banner_url"] = banner_url

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
        form.address.data = tournament_data.get("location")
        form.venue_name.data = tournament_data.get("venue_name")
        form.description.data = tournament_data.get("description")
        form.mode.data = (
            tournament_data.get("mode")
            or tournament_data.get("matchType", "SINGLES").upper()
        )
        raw_date = tournament_data.get("date")
        if hasattr(raw_date, "to_datetime"):
            form.start_date.data = raw_date.to_datetime().date()

    return render_template(
        "tournaments/create_edit.html",
        form=form,
        tournament=tournament_data,
        action="Edit",
    )

# ... (remaining routes for invite, delete, accept, decline, complete follow)