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

            location_data = {
                "name": form.venue_name.data,
                "address": form.address.data,
                "google_map_link": f"https://www.google.com/maps/search/?api=1&query={form.address.data}",
            }

            data = {
                "name": form.name.data,
                "start_date": date_val,
                "venue_name": form.venue_name.data,
                "address": form.address.data,
                "match_type": form.match_type.data,
                "format": form.format.data,
                "description": form.description.data,
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

        location_data = {
            "name": form.venue_name.data,
            "address": form.address.data,
            "google_map_link": f"https://www.google.com/maps/search/?api=1&query={form.address.data}",
        }

        update_data = {
            "name": form.name.data,
            "start_date": date_val,
            "venue_name": form.venue_name.data,
            "address": form.address.data,
            "match_type": form.match_type.data,
            "format": form.format.data,
            "description": form.description.data,
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
        form.venue_name.data = tournament_data.get("location")
        form.address.data = tournament_data.get("address")
        form.description.data = tournament_data.get("description")
        form.format.data = tournament_data.get("format")
        form.match_type.data = (
            tournament_data.get("mode")
            or tournament_data.get("matchType", "SINGLES").upper()
        )
        raw_date = tournament_data.get("date")
        if hasattr(raw_date, "to_datetime"):
            form.start_date.data = raw_date.to_datetime().date()

    logging.warning(f"Type of form in edit_tournament: {type(form)}")
    return render_template(
        "tournaments/create_edit.html",
        form=form,
        tournament=tournament_data,
        action="Edit",
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


@bp.route("/<string:tournament_id>/register_team", methods=["POST"])
@login_required
def register_team(tournament_id: str) -> Any:
    """Register a doubles team for the tournament."""
    # Check if it's an AJAX request (invite link generation)
    if request.is_json:
        data = request.get_json()
        team_name = data.get("team_name")
        partner_id = data.get("partner_id")  # Might be None for invite link
    else:
        partner_id = request.form.get("partner_id")
        team_name = request.form.get("team_name")

    try:
        team_id = TournamentService.register_team(
            tournament_id, g.user["uid"], partner_id, team_name
        )

        if request.is_json:
            invite_link = url_for(
                ".view_tournament",
                tournament_id=tournament_id,
                claim_team=team_id,
                _external=True,
            )
            return jsonify({"success": True, "team_id": team_id, "link": invite_link})

        if not partner_id:
            flash("Invite link generated!", "success")
        else:
            flash("Team registration pending. Your partner must accept.", "info")
    except Exception as e:
        if request.is_json:
            return jsonify({"success": False, "error": str(e)}), 400
        flash(f"Error registering team: {e}", "danger")

    return redirect(url_for(".view_tournament", tournament_id=tournament_id))


@bp.route("/<string:tournament_id>/claim_team/<string:team_id>", methods=["POST"])
@login_required
def claim_team(tournament_id: str, team_id: str) -> Any:
    """Claim a placeholder team partnership."""
    try:
        success = TournamentService.claim_team_partnership(
            tournament_id, team_id, g.user["uid"]
        )
        if success:
            flash("You have joined the team!", "success")
        else:
            flash(
                "Unable to join team. It may be full or you are already in it.",
                "danger",
            )
    except Exception as e:
        flash(f"Error: {e}", "danger")

    return redirect(url_for(".view_tournament", tournament_id=tournament_id))


@bp.route("/<string:tournament_id>/accept_team", methods=["POST"])
@login_required
def accept_team(tournament_id: str) -> Any:
    """Accept a team partnership invitation."""
    try:
        success = TournamentService.accept_team_partnership(
            tournament_id, g.user["uid"]
        )
        if success:
            flash("You have accepted the team partnership!", "success")
        else:
            flash("No pending partnership found.", "warning")
    except Exception as e:
        flash(f"Error: {e}", "danger")

    return redirect(url_for(".view_tournament", tournament_id=tournament_id))
