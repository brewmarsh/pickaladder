"""Routes for the teams blueprint."""

from __future__ import annotations

from typing import Any

from firebase_admin import firestore
from flask import Response, flash, g, redirect, render_template, request, url_for

from pickaladder.auth.decorators import login_required
from pickaladder.constants.messages import COMMON_MESSAGES, MATCH_MESSAGES

from . import bp
from .forms import EditTeamNameForm, TeamForm
from .repository import TeamRepository
from .services import TeamService


@bp.route("/create", methods=["GET", "POST"])
@login_required
def create_team() -> Response | str:
    """Create a new named team."""
    db = firestore.client()
    form = TeamForm()

    # Fetch all users for member selection
    # In a real app, this should be limited to friends or group members
    users_ref = db.collection("users")
    users = users_ref.stream()
    form.members.choices = [(u.id, u.to_dict().get("name", u.id)) for u in users]

    if form.validate_on_submit():
        try:
            member_ids = form.members.data
            # Ensure creator is in the team
            if g.user.uid not in member_ids:
                member_ids.append(g.user.uid)

            team_id = TeamService.create_named_team(
                db,
                form.name.data,
                g.user.uid,
                member_ids,
            )
            flash("Team created successfully!", "success")
            return redirect(url_for(".view_team", team_id=team_id))
        except Exception as e:
            flash(f"Error creating team: {e}", "danger")

    return render_template("team/create.html", form=form)


@bp.route("/<string:team_id>")
@login_required
def view_team(team_id: str) -> Response | str:
    """Display a single team's page."""
    db = firestore.client()
    data = TeamService.get_team_dashboard_data(db, team_id)

    if not data:
        flash(MATCH_MESSAGES["NOT_FOUND"], "danger")
        return redirect(url_for("group.view_groups"))

    return render_template("team/view.html", **data)


@bp.route("/<string:team_id>/edit", methods=["GET", "POST"])
@login_required
def rename_team(team_id: str) -> Response | str:
    """Edit a team's name."""
    db = firestore.client()
    team_ref = db.collection("teams").document(team_id)
    team = team_ref.get()

    if not team.exists:
        flash(MATCH_MESSAGES["NOT_FOUND"], "danger")
        return redirect(url_for("group.view_groups"))

    team_data = team.to_dict()
    team_data["id"] = team.id

    # Authorization check
    if g.user.uid not in team_data.get("member_ids", []):
        flash(MATCH_MESSAGES["RENAME_DENIED"], "danger")
        return redirect(url_for(".view_team", team_id=team_id))

    form = EditTeamNameForm()
    if form.validate_on_submit():
        try:
            team_ref.update({"name": form.name.data})
            flash(MATCH_MESSAGES["UPDATE_SUCCESS"], "success")
            return redirect(url_for(".view_team", team_id=team_id))
        except Exception as e:
            flash(COMMON_MESSAGES["UNEXPECTED_ERROR"].format(error=e), "danger")

    form.name.data = team_data.get("name")
    return render_template("team/edit.html", form=form, team=team_data)


@bp.route("/api/user-teams")
@login_required
def get_user_teams() -> dict[str, list[dict[str, Any]]]:
    """Fetch named teams for the current user."""
    db = firestore.client()
    teams = TeamService.get_user_named_teams(db, g.user.uid)
    # Simplify for JSON response
    result = []
    for team in teams:
        result.append(
            {
                "id": team["id"],
                "name": team.get("name", "Unnamed Team"),
                "member_ids": team.get("member_ids", []),
            },
        )
    return {"teams": result}


@bp.route("/api/<string:team_id>/roster")
@login_required
def get_team_roster(team_id: str) -> tuple[dict[str, Any], int] | dict[str, Any]:
    """Fetch the roster for a specific team."""
    db = firestore.client()
    team_data = TeamRepository.get_by_id(db, team_id)
    if not team_data:
        return {"error": "Team not found"}, 404

    # Authorization check
    if g.user.uid not in team_data.get("member_ids", []):
        return {"error": "Unauthorized"}, 403

    members = TeamService._fetch_team_members(db, team_data)
    # Simplify for JSON response
    result = []
    for member in members:
        result.append(
            {
                "id": member["id"],
                "name": member.get("name", member["id"]),
            },
        )
    return {"members": result}


@bp.route("/wizard", methods=["GET", "POST"])
@login_required
def team_wizard() -> Response | str | tuple[dict[str, Any], int] | dict[str, Any]:
    """Multi-step wizard for team creation."""
    db = firestore.client()

    if request.method == "POST":
        data = request.get_json()
        if not data:
            return {"error": "Invalid data"}, 400

        name = data.get("name")
        member_ids = data.get("member_ids", [])

        if not name:
            return {"error": "Team name is required"}, 400

        try:
            # Ensure creator is in the team
            if g.user.uid not in member_ids:
                member_ids.append(g.user.uid)

            team_id = TeamService.create_named_team(db, name, g.user.uid, member_ids)
            return {
                "success": True,
                "team_id": team_id,
                "redirect": url_for(".view_team", team_id=team_id),
            }
        except Exception as e:
            return {"error": str(e)}, 500

    # For GET, fetch potential members (all users for now, following create_team logic)
    users_ref = db.collection("users")
    users = users_ref.stream()
    member_choices = [
        {"id": u.id, "name": u.to_dict().get("name", u.to_dict().get("username", u.id))}
        for u in users
    ]

    return render_template("team/wizard.html", member_choices=member_choices)
