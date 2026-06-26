"""Routes for the tournament blueprint."""

from __future__ import annotations

import datetime
import logging
from typing import Any, cast

from firebase_admin import firestore
from flask import (
    Response,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from pickaladder.auth.decorators import admin_required, login_required
from pickaladder.constants.messages import COMMON_MESSAGES, TOURNAMENT_MESSAGES
from pickaladder.tournament.utils import aggregate_match_data, sort_and_format_standings
from pickaladder.user.helpers import smart_display_name

from . import bp
from .forms import InvitePlayerForm, TournamentForm
from .services import TournamentService

MIN_PARTICIPANTS_FOR_GENERATION = 2


@bp.route("/", methods=["GET"])
@login_required
def list_tournaments() -> str:
    """List all tournaments."""
    tourneys = TournamentService.list_tournaments(g.user.uid)
    return render_template("tournaments.html", tournaments=tourneys)


def _get_group_admin_error(group_id: str | None, user_uid: str) -> str | None:
    """Check if user has admin access to the group."""
    if not group_id:
        return None
    db = firestore.client()
    doc = cast("Any", db.collection("groups").document(group_id).get())
    if doc.exists:
        from pickaladder.group.services.group_service import GroupService

        if not GroupService.is_group_admin(doc.to_dict() or {}, user_uid):
            return TOURNAMENT_MESSAGES["GROUP_ADMIN_REQUIRED"]
    return None


def _handle_creation_payload(form: TournamentForm, user_uid: str) -> str:
    """Process tournament creation and return ID."""
    date_val = form.start_date.data
    if date_val is None:
        msg = "Date is required"
        raise ValueError(msg)
    data = {
        "name": form.name.data,
        "date": datetime.datetime.combine(date_val, datetime.time.min),
        "venue_name": form.venue_name.data,
        "address": form.address.data,
        "mode": form.match_type.data,
        "matchType": (form.match_type.data or "SINGLES").lower(),
        "format": form.format.data,
        "pool_count": int(form.pool_count.data or 0),
        "promoted_per_pool": int(form.promoted_per_pool.data or 0),
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
def create_tournament() -> Response | str:
    """Create a new tournament."""
    gid = request.args.get("group_id")
    error = _get_group_admin_error(gid, g.user.uid)
    if error:
        flash(error, "danger")
        return redirect(url_for("group.view_group", group_id=gid))

    form = TournamentForm()
    if form.validate_on_submit():
        try:
            t_id = _handle_creation_payload(form, g.user.uid)
            flash(TOURNAMENT_MESSAGES["CREATE_SUCCESS"], "success")
            return redirect(url_for(".view_tournament", tournament_id=t_id))
        except Exception as e:
            flash(COMMON_MESSAGES["UNEXPECTED_ERROR"].format(error=e), "danger")
    return render_template("tournaments/create_edit.html", form=form, action="Create")


def _resolve_claim_data(t_id: str, c_id: str | None) -> dict[str, Any] | None:
    """Fetch details for a team partnership claim."""
    if not c_id:
        return None
    db = firestore.client()
    ref = db.collection("tournaments").document(t_id).collection("teams").document(c_id)
    doc = cast("Any", ref.get())
    if not doc.exists:
        return None
    d = cast("dict[str, Any]", doc.to_dict() or {})
    d["id"] = doc.id
    p1_uid = d.get("p1_uid")
    if p1_uid:
        p1 = cast("Any", db.collection("users").document(p1_uid).get())
        d["p1_name"] = (
            smart_display_name(p1.to_dict() or {}) if p1.exists else "Someone"
        )
    else:
        d["p1_name"] = "Someone"
    return d


def _handle_view_invite(tournament_id: str, form: InvitePlayerForm) -> bool:
    """Handle invitation form submission from view page."""
    if form.validate_on_submit() and "user_id" in request.form:
        uid = cast("str", form.user_id.data)
        if uid:
            TournamentService.invite_player(tournament_id, g.user.uid, uid)
            return True
    return False


@bp.route("/<string:tournament_id>", methods=["GET", "POST"])
@login_required
def view_tournament(tournament_id: str) -> Response | str:
    """View a single tournament lobby."""
    details = TournamentService.get_tournament_details(tournament_id, g.user.uid)
    if not details:
        flash(TOURNAMENT_MESSAGES["NOT_FOUND"], "danger")
        return redirect(url_for(".list_tournaments"))

    details["claim_team_data"] = _resolve_claim_data(
        tournament_id,
        request.args.get("claim_team"),
    )
    form = InvitePlayerForm()
    invitables = details.get("invitable_users", [])
    form.user_id.choices = [(u["id"], smart_display_name(u)) for u in invitables]

    try:
        if _handle_view_invite(tournament_id, form):
            flash(TOURNAMENT_MESSAGES["PLAYER_INVITE_SUCCESS"], "success")
            return redirect(url_for(".view_tournament", tournament_id=tournament_id))
    except Exception as e:
        flash(TOURNAMENT_MESSAGES["INVITE_ERROR"].format(error=e), "danger")

    details["matches"] = TournamentService.get_tournament_matches(tournament_id)

    # Phase 28: Support for Pool Play Standings
    if details["tournament"].get("format") == "POOL_PLAY":
        pools = {}
        for m in details["matches"]:
            pool_id = m.get("pool_id")
            if pool_id:
                if pool_id not in pools:
                    pools[pool_id] = []
                pools[pool_id].append(m)

        pool_standings = {}
        db = firestore.client()
        for pool_id, pool_matches in pools.items():
            raw = aggregate_match_data(
                pool_matches,
                details["tournament"].get("matchType", "singles"),
            )
            pool_standings[pool_id] = sort_and_format_standings(
                db,
                raw,
                details["tournament"].get("matchType", "singles"),
            )

        details["pool_standings"] = pool_standings

    return render_template("tournament/view.html", invite_form=form, **details)


def _handle_tournament_update(tournament_id: str, form: TournamentForm) -> bool:
    """Process tournament update from form."""
    if form.validate_on_submit():
        TournamentService.update_tournament_from_form(
            tournament_id,
            g.user.uid,
            form.data,
            request.files.get("banner"),
        )
        return True
    return False


def _populate_edit_form(form: TournamentForm, tournament_data: dict[str, Any]) -> None:
    """Populate the edit form with existing tournament data."""
    form.process(data=tournament_data)
    form.match_type.data = tournament_data.get("mode", "SINGLES")
    t_date = tournament_data.get("date")
    if hasattr(t_date, "to_datetime"):
        form.start_date.data = cast("Any", t_date).to_datetime().date()


@bp.route("/<string:tournament_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_tournament(tournament_id: str) -> Response | str:
    """Edit tournament details."""
    form = TournamentForm()
    try:
        t = TournamentService.get_tournament_for_edit(tournament_id, g.user.uid)
        if _handle_tournament_update(tournament_id, form):
            flash(TOURNAMENT_MESSAGES["UPDATE_SUCCESS"], "success")
            return redirect(url_for(".view_tournament", tournament_id=tournament_id))

        if request.method == "GET":
            _populate_edit_form(form, t)

        return render_template(
            "tournaments/create_edit.html",
            form=form,
            tournament=t,
            action="Edit",
        )
    except (ValueError, PermissionError) as e:
        flash(str(e), "danger")
    except Exception as e:
        flash(COMMON_MESSAGES["UNEXPECTED_ERROR"].format(error=e), "danger")
    return redirect(url_for(".list_tournaments"))


@bp.route("/<string:tournament_id>/delete", methods=["POST"])
@admin_required
def delete_tournament(tournament_id: str) -> Response:
    """Delete a tournament."""
    try:
        TournamentService.delete_tournament(tournament_id, g.user.uid)
        flash(TOURNAMENT_MESSAGES["DELETE_SUCCESS"], "success")
    except (ValueError, PermissionError) as e:
        flash(str(e), "danger")
    except Exception as e:
        flash(COMMON_MESSAGES["UNEXPECTED_ERROR"].format(error=e), "danger")
    return redirect(url_for(".list_tournaments"))


@bp.route("/<string:tournament_id>/invite", methods=["POST"])
@login_required
def invite_player(tournament_id: str) -> Response:
    """Invite a player to a tournament."""
    form = InvitePlayerForm()
    uid = request.form.get("user_id")
    if uid:
        form.user_id.choices = [(uid, "")]
    if form.validate_on_submit():
        try:
            invited_uid = cast("str", form.user_id.data)
            TournamentService.invite_player(tournament_id, g.user.uid, invited_uid)
            flash(TOURNAMENT_MESSAGES["PLAYER_INVITE_SUCCESS"], "success")
        except Exception as e:
            flash(COMMON_MESSAGES["UNEXPECTED_ERROR"].format(error=e), "danger")
    return redirect(url_for(".view_tournament", tournament_id=tournament_id))


@bp.route("/<string:tournament_id>/invite_group", methods=["POST"])
@login_required
def invite_group(tournament_id: str) -> Response:
    """Invite an entire group."""
    gid = request.form.get("group_id")
    if not gid:
        flash(TOURNAMENT_MESSAGES["NO_GROUP_SPECIFIED"], "warning")
        return redirect(url_for(".view_tournament", tournament_id=tournament_id))
    try:
        count = TournamentService.invite_group(tournament_id, gid, g.user.uid)
        flash(
            TOURNAMENT_MESSAGES["INVITE_COUNT_SUCCESS"].format(count=count),
            "success",
        )
    except (ValueError, PermissionError) as e:
        flash(str(e), "danger")
    except Exception as e:
        flash(COMMON_MESSAGES["GENERIC_ERROR"].format(error=e), "danger")
    return redirect(url_for(".view_tournament", tournament_id=tournament_id))


@bp.route("/<string:tournament_id>/accept", methods=["POST"])
@login_required
def accept_invite(tournament_id: str) -> Response:
    """Accept an invite to a tournament."""
    try:
        if TournamentService.accept_invite(tournament_id, g.user.uid):
            flash(TOURNAMENT_MESSAGES["INVITE_ACCEPTED"], "success")
        else:
            flash(TOURNAMENT_MESSAGES["INVITE_NOT_FOUND_OR_ACCEPTED"], "warning")
    except Exception as e:
        flash(COMMON_MESSAGES["GENERIC_ERROR"].format(error=e), "danger")
    return redirect(request.referrer or url_for("user.dashboard"))


@bp.route("/<string:tournament_id>/decline", methods=["POST"])
@login_required
def decline_invite(tournament_id: str) -> Response:
    """Decline an invite to a tournament."""
    try:
        if TournamentService.decline_invite(tournament_id, g.user.uid):
            flash(TOURNAMENT_MESSAGES["INVITE_DECLINED"], "info")
        else:
            flash(TOURNAMENT_MESSAGES["INVITE_NOT_FOUND"], "warning")
    except Exception as e:
        flash(COMMON_MESSAGES["GENERIC_ERROR"].format(error=e), "danger")
    return redirect(request.referrer or url_for("user.dashboard"))


@bp.route("/<string:tournament_id>/complete", methods=["POST"])
@login_required
def complete_tournament(tournament_id: str) -> Response:
    """Close tournament and send results."""
    try:
        TournamentService.complete_tournament(tournament_id, g.user.uid)
        flash(TOURNAMENT_MESSAGES["COMPLETE_SUCCESS"], "success")
    except (ValueError, PermissionError) as e:
        flash(str(e), "danger")
    except Exception as e:
        flash(COMMON_MESSAGES["GENERIC_ERROR"].format(error=e), "danger")
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
    parts = cast("list[dict[str, Any]]", data.get("participants", []))
    return [uid for p in parts if (uid := _extract_uid_from_participant(p)) is not None]


@bp.route("/<string:tournament_id>/generate", methods=["POST"])
@login_required
def generate_bracket(tournament_id: str) -> Response:
    """Generate the tournament bracket/pairings."""
    if not g.user.is_admin:
        flash(TOURNAMENT_MESSAGES["ADMIN_ONLY_BRACKET"], "danger")
        return redirect(url_for(".view_tournament", tournament_id=tournament_id))

    try:
        count = TournamentService.publish_bracket(tournament_id, g.user.uid)
        if count > 0:
            flash(
                TOURNAMENT_MESSAGES["BRACKET_GEN_SUCCESS"].format(count=count),
                "success",
            )
        else:
            flash(TOURNAMENT_MESSAGES["MIN_PARTICIPANTS"], "warning")
    except (ValueError, PermissionError) as e:
        flash(str(e), "danger")
    except Exception as e:
        flash(
            TOURNAMENT_MESSAGES["GEN_NOT_IMPLEMENTED"].format(format="selected"),
            "warning",
        )
        logging.exception(f"Bracket gen failed: {e}")

    return redirect(url_for(".view_tournament", tournament_id=tournament_id))


@bp.route("/<string:tournament_id>/promote_pools", methods=["POST"])
@login_required
def promote_pools(tournament_id: str) -> Response:
    """Promote top performers to a single-elimination bracket."""
    try:
        count = TournamentService.promote_pools_to_bracket(tournament_id, g.user.uid)
        if count > 0:
            flash(
                f"Success! {count} players promoted to a single-elimination bracket.",
                "success",
            )
        else:
            flash(
                "Unable to generate bracket. Ensure all pool matches are completed.",
                "warning",
            )
    except (ValueError, PermissionError) as e:
        flash(str(e), "danger")
    except Exception as e:
        flash(f"Unexpected error during promotion: {e}", "danger")
        logging.exception(f"Pool promotion failed: {e}")

    return redirect(url_for(".view_tournament", tournament_id=tournament_id))


@bp.route("/<string:tournament_id>/join", methods=["POST"])
@login_required
def join_tournament(tournament_id: str) -> Response:
    """Accept tournament invitation (legacy alias)."""
    return accept_invite(tournament_id)


def _handle_registration(
    t_id: str,
    p_id: str | None,
    name: str,
    is_json: bool,
) -> Response | str:
    """Perform team registration and return response."""
    tid = TournamentService.register_team(t_id, g.user.uid, p_id, name)
    if is_json:
        url = url_for(
            ".view_tournament",
            tournament_id=t_id,
            claim_team=tid,
            _external=True,
        )
        return jsonify({"success": True, "team_id": tid, "link": url})

    if not p_id:
        flash(TOURNAMENT_MESSAGES["INVITE_LINK_GEN"], "success")
    else:
        flash(TOURNAMENT_MESSAGES["TEAM_REG_PENDING"], "info")
    return redirect(url_for(".view_tournament", tournament_id=t_id))


@bp.route("/<string:tournament_id>/register_team", methods=["POST"])
@login_required
def register_team(tournament_id: str) -> Response | str:
    """Register a doubles team for the tournament."""
    is_json = request.is_json
    data = cast("dict[str, Any]", request.get_json() if is_json else request.form)
    try:
        p_id = data.get("partner_id")
        t_name = cast("str", data.get("team_name") or "")
        return _handle_registration(
            tournament_id,
            cast("str", p_id) if p_id else None,
            t_name,
            is_json,
        )
    except Exception as e:
        if is_json:
            return jsonify({"success": False, "error": str(e)}), 400
        flash(TOURNAMENT_MESSAGES["TEAM_REG_ERROR"].format(error=e), "danger")
    return redirect(url_for(".view_tournament", tournament_id=tournament_id))


@bp.route("/<string:tournament_id>/claim_team/<string:team_id>", methods=["POST"])
@login_required
def claim_team(tournament_id: str, team_id: str) -> Response:
    """Claim a placeholder team partnership."""
    try:
        if TournamentService.claim_team_partnership(tournament_id, team_id, g.user.uid):
            flash(TOURNAMENT_MESSAGES["JOIN_TEAM_SUCCESS"], "success")
        else:
            flash(TOURNAMENT_MESSAGES["JOIN_TEAM_FAILED"], "danger")
    except Exception as e:
        flash(COMMON_MESSAGES["GENERIC_ERROR"].format(error=e), "danger")
    return redirect(url_for(".view_tournament", tournament_id=tournament_id))


@bp.route("/<string:tournament_id>/accept_team", methods=["POST"])
@login_required
def accept_team(tournament_id: str) -> Response:
    """Accept a team partnership invitation."""
    try:
        if TournamentService.accept_team_partnership(tournament_id, g.user.uid):
            flash(TOURNAMENT_MESSAGES["PARTNERSHIP_ACCEPTED"], "success")
        else:
            flash(TOURNAMENT_MESSAGES["NO_PENDING_PARTNERSHIP"], "warning")
    except Exception as e:
        flash(COMMON_MESSAGES["GENERIC_ERROR"].format(error=e), "danger")
    return redirect(url_for(".view_tournament", tournament_id=tournament_id))
