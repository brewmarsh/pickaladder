"""Routes for the tournament blueprint."""

from __future__ import annotations

import datetime
from typing import Any

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
from pickaladder.services import TournamentService
from pickaladder.user.utils import smart_display_name

from . import bp
from .forms import InvitePlayerForm, TournamentForm


@bp.route("/", methods=["GET"])
@login_required
def list_tournaments() -> Any:
    """List all tournaments."""
    tournaments = TournamentService.list_tournaments(g.user["uid"])
    return render_template("tournaments.html", tournaments=tournaments)


@bp.route("/create", methods=["GET", "POST"])
@login_required
def create_tournament() -> Any:
    """Create a new tournament."""
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
            }
            new_id = TournamentService.create_tournament(data, g.user["uid"])
            flash("Tournament created successfully.", "success")
            return redirect(url_for(".view_tournament", tournament_id=new_id))
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

    # Prepare Invite Form
    invite_form = InvitePlayerForm()
    invite_form.user_id.choices = [
        (u["id"], smart_display_name(u)) for u in details["invitable_users"]
    ]

    # Handle Inline Invite Submission
    if invite_form.validate_on_submit() and "user_id" in request.form:
        try:
            TournamentService.invite_player(
                tournament_id, g.user["uid"], invite_form.user_id.data
            )
            flash("Player invited successfully.", "success")
            return redirect(url_for(".view_tournament", tournament_id=tournament_id))
        except Exception as e:
            flash(f"Error sending invite: {e}", "danger")

    return render_template(
        "tournament/view.html",
        tournament=details["tournament"],
        participants=details["participants"],
        standings=details["standings"],
        podium=details["podium"],
        invite_form=invite_form,
        invitable_users=details["invitable_users"],
        user_groups=details["user_groups"],
        is_owner=details["is_owner"],
    )


@bp.route("/<string:tournament_id>/edit", methods=["GET", "POST"])
@login_required
def edit_tournament(tournament_id: str) -> Any:
    """Edit tournament details."""
    # We fetch view data to populate GET request (reuse service for efficiency)
    details = TournamentService.get_tournament_details(tournament_id, g.user["uid"])
    if not details:
        flash("Tournament not found.", "danger")
        return redirect(url_for(".list_tournaments"))

    if not details["is_owner"]:
        flash("Unauthorized.", "danger")
        return redirect(url_for(".view_tournament", tournament_id=tournament_id))

    form = TournamentForm()
    if form.validate_on_submit():
        date_val = form.date.data
        if date_val is None:
            flash("Date is required.", "danger")
            return render_template(
                "tournament/edit.html", form=form, tournament=details["tournament"]
            )

        update_data = {
            "name": form.name.data,
            "date": datetime.datetime.combine(date_val, datetime.time.min),
            "location": form.location.data,
            "matchType": form.match_type.data,
        }

        try:
            TournamentService.update_tournament(
                tournament_id, g.user["uid"], update_data
            )
            flash("Updated!", "success")
            return redirect(url_for(".view_tournament", tournament_id=tournament_id))
        except Exception as e:
            flash(f"Update failed: {e}", "danger")

    elif request.method == "GET":
        t_data = details["tournament"]
        form.name.data = t_data.get("name")
        form.location.data = t_data.get("location")
        form.match_type.data = t_data.get("matchType")
        raw_date = t_data.get("date")
        if raw_date and hasattr(raw_date, "to_datetime"):
            form.date.data = raw_date.to_datetime().date()

    return render_template(
        "tournament/edit.html", form=form, tournament=details["tournament"]
    )


@bp.route("/<string:tournament_id>/invite", methods=["GET", "POST"])
@login_required
def invite_player(tournament_id: str) -> Any:
    """Invites a player (Endpoint used by the form)."""
    if request.method == "GET":
        return redirect(url_for(".view_tournament", tournament_id=tournament_id))

    user_id = request.form.get("user_id")
    if not user_id:
        flash("No player selected.", "danger")
        return redirect(url_for(".view_tournament", tournament_id=tournament_id))

    try:
        TournamentService.invite_player(tournament_id, g.user["uid"], user_id)
        flash("Invite sent!", "success")
    except Exception as e:
        flash(f"Error: {e}", "danger")

    return redirect(url_for(".view_tournament", tournament_id=tournament_id))


@bp.route("/<string:tournament_id>/invite_group", methods=["POST"])
@login_required
def invite_group(tournament_id: str) -> Any:
    """Invites all members of a group."""
    group_id = request.form.get("group_id")
    if not group_id:
        flash("No group selected.", "danger")
        return redirect(url_for(".view_tournament", tournament_id=tournament_id))

    try:
        count = TournamentService.invite_group(tournament_id, group_id, g.user["uid"])
        if count > 0:
            flash(f"Invited {count} members from the group.", "success")
        else:
            flash("All group members are already in the tournament.", "info")
    except (ValueError, PermissionError) as e:
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.error(f"Group invite error: {e}")
        flash("An unexpected error occurred.", "danger")

    return redirect(url_for(".view_tournament", tournament_id=tournament_id))


@bp.route("/<string:tournament_id>/accept", methods=["POST"])
@login_required
def accept_invite(tournament_id: str) -> Any:
    """Accept an invite."""
    if TournamentService.accept_invite(tournament_id, g.user["uid"]):
        flash("You have accepted the tournament invite!", "success")
    else:
        flash("Invite not found or already accepted.", "warning")
    return redirect(request.referrer or url_for("user.dashboard"))


@bp.route("/<string:tournament_id>/decline", methods=["POST"])
@login_required
def decline_invite(tournament_id: str) -> Any:
    """Decline an invite."""
    if TournamentService.decline_invite(tournament_id, g.user["uid"]):
        flash("You have declined the tournament invite.", "info")
    else:
        flash("Invite not found.", "warning")
    return redirect(request.referrer or url_for("user.dashboard"))


@bp.route("/<string:tournament_id>/complete", methods=["POST"])
@login_required
def complete_tournament(tournament_id: str) -> Any:
    """Close tournament."""
    try:
        TournamentService.complete_tournament(tournament_id, g.user["uid"])
        flash("Tournament completed and results emailed!", "success")
    except (ValueError, PermissionError) as e:
        flash(str(e), "danger")
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")
    return redirect(url_for(".view_tournament", tournament_id=tournament_id))


@bp.route("/<string:tournament_id>/join", methods=["POST"])
@login_required
def join_tournament(tournament_id: str) -> Any:
    """Legacy alias for accept."""
    return accept_invite(tournament_id)
