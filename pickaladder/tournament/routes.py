"""Routes for the tournament blueprint."""

from __future__ import annotations

from typing import Any, cast

from flask import (
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

from pickaladder.auth.decorators import login_required
from pickaladder.user.utils import smart_display_name

from . import bp
from .forms import InvitePlayerForm, TournamentForm
from .services import TournamentService


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

            tournament_id = TournamentService.create_tournament(
                cast(str, g.user["uid"]),
                cast(str, form.name.data),
                date_val,
                cast(str, form.location.data),
                cast(str, form.match_type.data),
            )
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

    if details is None:
        flash("Tournament not found.", "danger")
        return redirect(url_for(".list_tournaments"))

    # Handle Invitations
    invite_form = InvitePlayerForm()
    invite_form.user_id.choices = [
        (u["id"], smart_display_name(u)) for u in details["invitable_users"]
    ]

    # Handle Invite Form Submission from the view page itself
    if invite_form.validate_on_submit() and "user_id" in request.form:
        invited_uid = invite_form.user_id.data
        try:
            TournamentService.invite_player(tournament_id, invited_uid)
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
    tournament_data = TournamentService.get_tournament(tournament_id)

    if tournament_data is None:
        flash("Tournament not found.", "danger")
        return redirect(url_for(".list_tournaments"))

    form = TournamentForm()
    if form.validate_on_submit():
        date_val = form.date.data
        if date_val is None:
            flash("Date is required.", "danger")
            return render_template(
                "tournament/edit.html", form=form, tournament=tournament_data
            )

        success, message = TournamentService.update_tournament_details(
            tournament_id,
            cast(str, g.user["uid"]),
            cast(str, form.name.data),
            date_val,
            cast(str, form.location.data),
            cast(str, form.match_type.data),
        )
        if success:
            flash(message, "success")
            return redirect(url_for(".view_tournament", tournament_id=tournament_id))
        else:
            flash(message, "danger")
            if message == "Unauthorized.":
                return redirect(
                    url_for(".view_tournament", tournament_id=tournament_id)
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
def invite_player(tournament_id: str) -> Any:
    """Invites a player (Endpoint used by the form)."""
    if request.method == "GET":
        return redirect(url_for(".view_tournament", tournament_id=tournament_id))

    user_id = request.form.get("user_id")
    if not user_id:
        flash("No player selected.", "danger")
        return redirect(url_for(".view_tournament", tournament_id=tournament_id))

    try:
        TournamentService.invite_player(tournament_id, user_id)
        flash("Invite sent!", "success")
    except Exception as e:
        flash(f"Error: {e}", "danger")

    return redirect(url_for(".view_tournament", tournament_id=tournament_id))


@bp.route("/<string:tournament_id>/invite_group", methods=["POST"])
@login_required
def invite_group(tournament_id: str) -> Any:
    """Invites all members of a group to a tournament."""
    group_id = request.form.get("group_id")
    if not group_id:
        flash("No group selected.", "danger")
        return redirect(url_for(".view_tournament", tournament_id=tournament_id))

    try:
        count, group_name = TournamentService.invite_group(tournament_id, group_id)
        if count > 0:
            flash(f"Success! Invited {count} members from {group_name}.", "success")
        else:
            flash(
                f"All members from '{group_name}' are already in the tournament.",
                "info",
            )
    except Exception as e:
        flash(f"Error: {e}", "danger")

    return redirect(url_for(".view_tournament", tournament_id=tournament_id))


@bp.route("/<string:tournament_id>/accept", methods=["POST"])
@login_required
def accept_invite(tournament_id: str) -> Any:
    """Accept an invite to a tournament using a transaction."""
    success = TournamentService.accept_invite(tournament_id, g.user["uid"])

    if success:
        flash("You have accepted the tournament invite!", "success")
    else:
        flash("Invite not found or already accepted.", "warning")

    return redirect(request.referrer or url_for("user.dashboard"))


@bp.route("/<string:tournament_id>/decline", methods=["POST"])
@login_required
def decline_invite(tournament_id: str) -> Any:
    """Decline an invite to a tournament using a transaction."""
    success = TournamentService.decline_invite(tournament_id, g.user["uid"])

    if success:
        flash("You have declined the tournament invite.", "info")
    else:
        flash("Invite not found.", "warning")

    return redirect(request.referrer or url_for("user.dashboard"))


@bp.route("/<string:tournament_id>/complete", methods=["POST"])
@login_required
def complete_tournament(tournament_id: str) -> Any:
    """Close tournament and send results to all participants."""
    success, message = TournamentService.complete_tournament(
        tournament_id, g.user["uid"]
    )
    if success:
        flash(message, "success")
    else:
        flash(message, "danger")

    return redirect(url_for(".view_tournament", tournament_id=tournament_id))


@bp.route("/<string:tournament_id>/join", methods=["POST"])
@login_required
def join_tournament(tournament_id: str) -> Any:
    """Accept tournament invitation (legacy alias)."""
    return accept_invite(tournament_id)
