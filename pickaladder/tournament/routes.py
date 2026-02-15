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

# ... (list_tournaments route remains unchanged)

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

            # Combine logic: use standardized location string but also 
            # capture structured location_data for maps integration.
            location_str = form.address.data or form.location.data
            
            data = {
                "name": form.name.data,
                "date": datetime.datetime.combine(date_val, datetime.time.min),
                "location": location_str,
                "location_data": {
                    "name": form.venue_name.data,
                    "address": form.address.data
                },
                "mode": form.mode.data,
                "matchType": form.mode.data.lower(),
                "venue_name": form.venue_name.data,
                "description": form.description.data,
            }
            tournament_id = TournamentService.create_tournament(data, g.user["uid"])

            # Handle banner upload
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

# ... (view_tournament remains same)

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

        location_str = form.address.data or form.location.data

        update_data = {
            "name": form.name.data,
            "date": datetime.datetime.combine(date_val, datetime.time.min),
            "location": location_str,
            "location_data": {
                "name": form.venue_name.data,
                "address": form.address.data
            },
            "mode": form.mode.data,
            "matchType": form.mode.data.lower(),
            "venue_name": form.venue_name.data,
            "description": form.description.data,
        }

        # ... (Upload logic remains unchanged)

        try:
            TournamentService.update_tournament(
                tournament_id, g.user["uid"], update_data
            )
            flash("Tournament updated successfully.", "success")
            return redirect(url_for(".view_tournament", tournament_id=tournament_id))
        except Exception as e:
            flash(f"An error occurred: {e}", "danger")

    # ... (GET initialization remains same)