"""Routes for the tournament blueprint."""

from __future__ import annotations

import datetime
import logging
from typing import Any, cast

from firebase_admin import firestore
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

logger = logging.getLogger(__name__)

@bp.route("/", methods=["GET"])
@login_required
def list_tournaments() -> Any:
    """List all tournaments."""
    tourneys = TournamentService.list_tournaments(g.user["uid"])
    return render_template("tournament/list.html", tournaments=tourneys)


def _get_group_admin_error(group_id: str | None, user_uid: str) -> str | None:
    """Check if user has admin access to the group."""
    if not group_id:
        return None
    db = firestore.client()
    doc = cast(Any, db.collection("groups").document(group_id).get())
    if doc.exists:
        from pickaladder.group.services.group_service import GroupService

        if not GroupService.is_group_admin(doc.to_dict() or {}, user_uid):
            return "You do not have permission to create a tournament for this group."
    return None


def _handle_creation_payload(form: TournamentForm, user_uid: str) -> str:
    """Process tournament creation and return ID."""
    date_val = form.start_date.data
    if date_val is None:
        raise ValueError("Date is required")
    data = {
        "name": form.name.data,
        "date": datetime.datetime.combine(date_val, datetime.time.min),
        "venue_name": form.venue_name.data,
        "address": form.address.data,
        "matchType": form.match_type.data,
        "mode": (form.match_type.data or "singles").upper(),
    }
    t_id = TournamentService.create_tournament(data, user_uid)
    banner = request.files.get("banner")
    if banner and banner.filename:
        url = TournamentService._upload_banner(t_id, banner)
        if url:
            TournamentService.update_tournament(t_id, user_uid, {"banner_url": url})
    return t_id


@bp.route("/create", methods=["GET", "POST"])
@admin_required
def create_tournament() -> Any:
    """Create a new tournament."""
    gid = request.args.get("group_id")
    error = _get_group_admin_error(gid, g.user["uid"])
    if error:
        flash(error, "danger")
        return redirect(url_for("group.view_group", group_id=gid))

    form = TournamentForm()
    if form.validate_on_submit():
        try:
            t_id = _handle_creation_payload(form, g.user["uid"])
            flash("Tournament created successfully.", "success")
            return redirect(url_for(".view_tournament", tournament_id=t_id))
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")
    return render_template("tournaments/create_edit.html", form=form, action="Create")


def _resolve_claim_data(t_id: str, c_id: str | None) -> dict[str, Any] | None:
    """Resolve team and participant data for partnership claim."""
    if not c_id:
        return None
    db = firestore.client()
    team_doc = db.collection("tournaments").document(t_id).collection("teams").document(c_id).get()
    if not team_doc.exists:
        return None

    td = cast(dict[str, Any], team_doc.to_dict())
    if td.get("p2_uid") or td.get("status") == "CONFIRMED":
        return None

    p1_doc = db.collection("users").document(td["p1_uid"]).get()
    if not p1_doc.exists:
        return None

    return {
        "id": c_id,
        "team_name": td.get("team_name") or "Unnamed Team",
        "p1_name": smart_display_name(p1_doc.to_dict() or {}),
    }


def _handle_view_invite(t_id: str, form: InvitePlayerForm) -> bool:
    """Handle invite submission from view page."""
    if form.validate_on_submit():
        invited_uid = cast(str, form.user_id.data)
        TournamentService.invite_player(t_id, g.user["uid"], invited_uid)
        return True
    return False


@bp.route("/<string:tournament_id>")
@login_required
def view_tournament(tournament_id: str) -> Any:
    """View tournament details."""
    details = TournamentService.get_tournament_details(tournament_id, g.user["uid"])
    if not details:
        flash("Tournament not found.", "danger")
        return redirect(url_for(".list_tournaments"))

    claim_id = request.args.get("claim_team")
    details["claim_team_data"] = _resolve_claim_data(tournament_id, claim_id)

    form = InvitePlayerForm()
    invitables = details.get("invitable_users", [])
    form.user_id.choices = [(u["id"], smart_display_name(u)) for u in invitables]

    try:
        if _handle_view_invite(tournament_id, form):
            flash("Player invited successfully.", "success")
            return redirect(url_for(".view_tournament", tournament_id=tournament_id))
    except Exception as e:
        flash(f"Error sending invite: {e}", "danger")

    return render_template("tournament/view.html", invite_form=form, **details)


def _handle_tournament_update(tournament_id: str, form: TournamentForm) -> bool:
    """Process tournament update from form."""
    if form.validate_on_submit():
        TournamentService.update_tournament_from_form(
            tournament_id, g.user["uid"], form.data, request.files.get("banner")
        )
        return True
    return False


def _populate_edit_form(form: TournamentForm, tournament_data: dict[str, Any]) -> None:
    """Populate the edit form with existing tournament data."""
    form.process(data=tournament_data)
    t_date = tournament_data.get("date")
    if hasattr(t_date, "to_datetime"):
        form.start_date.data = cast(Any, t_date).to_datetime().date()


@bp.route("/<string:tournament_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_tournament(tournament_id: str) -> Any:
    """Edit tournament details."""
    form = TournamentForm()
    try:
        t = TournamentService.get_tournament_for_edit(tournament_id, g.user["uid"])
        if _handle_tournament_update(tournament_id, form):
            flash("Tournament updated successfully.", "success")
            return redirect(url_for(".view_tournament", tournament_id=tournament_id))

        if request.method == "GET":
            _populate_edit_form(form, t)

        return render_template(
            "tournaments/create_edit.html", form=form, tournament=t, action="Edit"
        )
    except (ValueError, PermissionError) as e:
        flash(str(e), "danger")
    except Exception as e:
        flash(f"An unexpected error occurred: {e}", "danger")
    return redirect(url_for(".list_tournaments"))


@bp.route("/<string:tournament_id>/delete", methods=["POST"])
@admin_required
def delete_tournament(tournament_id: str) -> Any:
    """Delete a tournament."""
    try:
        TournamentService.delete_tournament(tournament_id, g.user["uid"])
        flash("Tournament deleted successfully.", "success")
    except (ValueError, PermissionError) as e:
        flash(str(e), "danger")
    except Exception as e:
        flash(f"An unexpected error occurred: {e}", "danger")
    return redirect(url_for(".list_tournaments"))


@bp.route("/<string:tournament_id>/invite", methods=["POST"])
@login_required
def invite_player(tournament_id: str) -> Any:
    """Invite a player to a tournament."""
    form = InvitePlayerForm()
    uid = request.form.get("user_id")
    if uid:
        form.user_id.choices = [(uid, "")]
    if form.validate_on_submit():
        try:
            invited_uid = cast(str, form.user_id.data)
            TournamentService.invite_player(tournament_id, g.user["uid"], invited_uid)
            flash("Player invited successfully.", "success")
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")
    return redirect(url_for(".view_tournament", tournament_id=tournament_id))


@bp.route("/<string:tournament_id>/invite_group", methods=["POST"])
@login_required
def invite_group(tournament_id: str) -> Any:
    """Invite an entire group."""
    gid = request.form.get("group_id")
    if not gid:
        flash("No group specified.", "warning")
        return redirect(url_for(".view_tournament", tournament_id=tournament_id))
    try:
        count = TournamentService.invite_group(tournament_id, gid, g.user["uid"])
        flash(f"Success! Invited {count} members.", "success")
    except (ValueError, PermissionError) as e:
        flash(str(e), "danger")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    return redirect(url_for(".view_tournament", tournament_id=tournament_id))


@bp.route("/<string:tournament_id>/accept", methods=["POST"])
@login_required
def accept_invite(tournament_id: str) -> Any:
    """Accept an invite to a tournament."""
    try:
        if TournamentService.accept_invite(tournament_id, g.user["uid"]):
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
        if TournamentService.decline_invite(tournament_id, g.user["uid"]):
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
    except (ValueError, PermissionError) as e:
        flash(str(e), "danger")
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")
    return redirect(url_for(".view_tournament", tournament_id=tournament_id))


def _extract_uid_from_participant(participant: dict[str, Any]) -> str | None:
    """Extract UID from a participant record."""
    if participant.get("status") != "accepted":
        return None

    u_ref = participant.get("userRef")
    if u_ref:
        return str(u_ref.id)

    uid = participant.get("user_id")
    return str(uid) if uid else None


def _get_accepted_uids(data: dict[str, Any]) -> list[str]:
    """Extract list of UIDs for accepted participants."""
    parts = cast(list[dict[str, Any]], data.get("participants", []))
    uids = [uid for p in parts if (uid := _extract_uid_from_participant(p)) is not None]
    return uids


@bp.route("/<string:tournament_id>/generate", methods=["POST"])
@login_required
def generate_bracket(tournament_id: str) -> Any:
    """Generate the tournament bracket/pairings."""
    if not g.user.get("isAdmin"):
        flash("Only admins can generate brackets.", "danger")
        return redirect(url_for(".view_tournament", tournament_id=tournament_id))

    db = firestore.client()
    doc = cast(Any, db.collection("tournaments").document(tournament_id).get())
    if not doc.exists:
        flash("Tournament not found.", "danger")
        return redirect(url_for(".list_tournaments"))

    d = cast(dict[str, Any], doc.to_dict() or {})
    if d.get("format") != "ROUND_ROBIN":
        flash(f"Generation for {d.get('format')} is not implemented.", "warning")
        return redirect(url_for(".view_tournament", tournament_id=tournament_id))

    uids = _get_accepted_uids(d)
    if len(uids) < 2:
        flash("At least 2 accepted participants are required.", "warning")
        return redirect(url_for(".view_tournament", tournament_id=tournament_id))

    count = TournamentService.save_pairings(
        tournament_id, TournamentGenerator.generate_round_robin(uids)
    )
    flash(f"Round Robin bracket generated with {count} matches!", "success")
    return redirect(url_for(".view_tournament", tournament_id=tournament_id))


@bp.route("/<string:tournament_id>/join", methods=["POST"])
@login_required
def join_tournament(tournament_id: str) -> Any:
    """Accept tournament invitation (legacy alias)."""
    return accept_invite(tournament_id)


def _handle_registration(t_id: str, p_id: str | None, name: str, is_json: bool) -> Any:
    """Perform team registration and return response."""
    tid = TournamentService.register_team(t_id, g.user["uid"], p_id, name)
    if is_json:
        url = url_for(
            ".view_tournament", tournament_id=t_id, claim_team=tid, _external=True
        )
        return jsonify({"success": True, "team_id": tid, "link": url})

    if not p_id:
        flash("Invite link generated!", "success")
    else:
        flash("Team registration pending. Your partner must accept.", "info")
    return redirect(url_for(".view_tournament", tournament_id=t_id))


@bp.route("/<string:tournament_id>/register_team", methods=["POST"])
@login_required
def register_team(tournament_id: str) -> Any:
    """Register a doubles team for the tournament."""
    is_json = request.is_json
    data = cast(dict[str, Any], request.get_json() if is_json else request.form)
    try:
        p_id = data.get("partner_id")
        t_name = cast(str, data.get("team_name") or "")
        return _handle_registration(
            tournament_id, cast(str, p_id) if p_id else None, t_name, is_json
        )
    except Exception as e:
        if is_json:
            return jsonify({"success": False, "error": str(e)}), 400
        flash(f"Error registering team: {e}", "danger")
    return redirect(url_for(".view_tournament", tournament_id=tournament_id))


@bp.route("/<string:tournament_id>/claim_team/<string:team_id>", methods=["POST"])
@login_required
def claim_team(tournament_id: str, team_id: str) -> Any:
    """Claim a placeholder team partnership."""
    try:
        if TournamentService.claim_team_partnership(
            tournament_id, team_id, g.user["uid"]
        ):
            flash("You have joined the team!", "success")
        else:
            flash("Unable to join team. Full or already in it.", "danger")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    return redirect(url_for(".view_tournament", tournament_id=tournament_id))


@bp.route("/<string:tournament_id>/accept_team", methods=["POST"])
@login_required
def accept_team(tournament_id: str) -> Any:
    """Accept a team partnership invitation."""
    try:
        if TournamentService.accept_team_partnership(tournament_id, g.user["uid"]):
            flash("You have accepted the team partnership!", "success")
        else:
            flash("No pending partnership found.", "warning")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    return redirect(url_for(".view_tournament", tournament_id=tournament_id))
