"""Routes for the tournament blueprint."""

from __future__ import annotations

import datetime
from typing import Any

from flask import (
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

from pickaladder.auth.decorators import login_required
from pickaladder.tournament.services import TournamentService
from pickaladder.user.services import UserService

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
        (u["id"], UserService.smart_display_name(u)) for u in invitable_users
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
@login_required
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
    # Dynamically set choices to allow validation
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


@bp.route("/<string:tournament_id>/join", methods=["POST"])
@login_required
def join_tournament(tournament_id: str) -> Any:
    """Accept tournament invitation (legacy alias)."""
    return accept_invite(tournament_id)