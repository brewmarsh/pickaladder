"""Routes for the tournament blueprint."""

from __future__ import annotations

import datetime
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

# ... (list_tournaments remains same)

@bp.route("/create", methods=["GET", "POST"])
@admin_required
def create_tournament() -> Any:
    """Create a new tournament."""
    # ... (Group admin check remains same)

    form = TournamentForm()
    if form.validate_on_submit():
        try:
            # Merged Logic: Use start_date or date fallback
            date_val = form.start_date.data or form.date.data
            if date_val is None:
                raise ValueError("Date is required")

            # Fallback for mode vs match_type from fix branch
            mode_val = form.match_type.data or form.mode.data or "SINGLES"

            # Enriched Location Data from main branch
            venue_name = form.venue_name.data or form.location.data or "Unknown Venue"
            address = form.address.data or venue_name
            location_data = {
                "name": venue_name,
                "address": address,
                "google_map_link": f"https://www.google.com/maps/search/?api=1&query={address}",
            }

            data = {
                "name": form.name.data,
                "date": datetime.datetime.combine(date_val, datetime.time.min),
                "location": venue_name,
                "mode": mode_val,
                "matchType": mode_val.lower(),
                "location_data": location_data,
                "description": form.description.data,
                "format": form.format.data,
            }
            tournament_id = TournamentService.create_tournament(data, g.user["uid"])

            # Banner upload logic...
            flash("Tournament created successfully.", "success")
            return redirect(url_for(".view_tournament", tournament_id=tournament_id))
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")

    return render_template("tournaments/create_edit.html", form=form, action="Create")

@bp.route("/<string:tournament_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_tournament(tournament_id: str) -> Any:
    """Edit tournament details with fallback support."""
    details = TournamentService.get_tournament_details(tournament_id, g.user["uid"])
    if not details:
        flash("Tournament not found.", "danger")
        return redirect(url_for(".list_tournaments"))

    if not details["is_owner"] and not g.user.get("isAdmin"):
        flash("Unauthorized.", "danger")
        return redirect(url_for(".view_tournament", tournament_id=tournament_id))

    tournament_data = details["tournament"]
    form = TournamentForm()

    if form.validate_on_submit():
        date_val = form.start_date.data or form.date.data
        if date_val is None:
            flash("Date is required.", "danger")
            return render_template("tournaments/create_edit.html", form=form, tournament=tournament_data, action="Edit")

        mode_val = form.match_type.data or form.mode.data or "SINGLES"
        venue_name = form.venue_name.data or form.location.data or "Unknown Venue"
        address = form.address.data or venue_name

        update_data = {
            "name": form.name.data,
            "date": datetime.datetime.combine(date_val, datetime.time.min),
            "location": venue_name,
            "mode": mode_val,
            "matchType": mode_val.lower(),
            "location_data": {
                "name": venue_name,
                "address": address,
                "google_map_link": f"https://www.google.com/maps/search/?api=1&query={address}",
            },
            "description": form.description.data,
            "format": form.format.data,
        }

        # Handle banner upload...
        try:
            TournamentService.update_tournament(tournament_id, g.user["uid"], update_data)
            flash("Tournament updated successfully.", "success")
            return redirect(url_for(".view_tournament", tournament_id=tournament_id))
        except Exception as e:
            flash(f"An error occurred: {e}", "danger")

    if request.method == "GET":
        # Pre-populate form fields using safety logic from main branch
        t_date = tournament_data.get("date")
        if t_date:
            if hasattr(t_date, "to_datetime"):
                form.start_date.data = t_date.to_datetime().date()
            elif isinstance(t_date, datetime.datetime):
                form.start_date.data = t_date.date()
            form.date.data = form.start_date.data

        form.name.data = tournament_data.get("name")
        form.venue_name.data = tournament_data.get("location_data", {}).get("name") or tournament_data.get("location")
        form.location.data = form.venue_name.data
        form.address.data = tournament_data.get("location_data", {}).get("address")
        form.match_type.data = tournament_data.get("mode") or tournament_data.get("matchType", "SINGLES").upper()
        form.mode.data = form.match_type.data
        form.description.data = tournament_data.get("description")
        form.format.data = tournament_data.get("format")

    return render_template("tournaments/create_edit.html", form=form, tournament=tournament_data, action="Edit")

@bp.route("/<string:tournament_id>/delete", methods=["POST"])
@admin_required
def delete_tournament(tournament_id: str) -> Any:
    """Delete a tournament (Restored from fix branch)."""
    db = firestore.client()
    try:
        db.collection("tournaments").document(tournament_id).delete()
        flash("Tournament deleted successfully.", "success")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    return redirect(url_for(".list_tournaments"))

# ... (remaining routes for accept/decline/generate remain unchanged)