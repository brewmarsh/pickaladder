"""Routes for the teams blueprint."""

from __future__ import annotations

from typing import Any

from firebase_admin import firestore
from flask import flash, g, redirect, render_template, url_for

from pickaladder.auth.decorators import login_required

from . import bp
from .forms import EditTeamNameForm
from .services import TeamService


@bp.route("/<string:team_id>")
@login_required
def view_team(team_id: str) -> Any:
    """Display a single team's page."""
    db = firestore.client()
    data = TeamService.get_team_dashboard_data(db, team_id)

    if not data:
        flash("Team not found.", "danger")
        return redirect(url_for("group.view_groups"))

    return render_template("team/view.html", **data)


@bp.route("/<string:team_id>/edit", methods=["GET", "POST"])
@login_required
def edit_team(team_id: str) -> Any:
    """Edit a team's name."""
    db = firestore.client()
    team_ref = db.collection("teams").document(team_id)
    team = team_ref.get()

    if not team.exists:
        flash("Team not found.", "danger")
        return redirect(url_for("group.view_groups"))

    team_data = team.to_dict()
    team_data["id"] = team.id

    # Authorization check
    if g.user["uid"] not in team_data.get("member_ids", []):
        flash("You do not have permission to rename this team.", "danger")
        return redirect(url_for(".view_team", team_id=team_id))

    form = EditTeamNameForm()
    if form.validate_on_submit():
        try:
            team_ref.update({"name": form.name.data})
            flash("Team renamed successfully.", "success")
            return redirect(url_for(".view_team", team_id=team_id))
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")

    form.name.data = team_data.get("name")
    return render_template("team/edit.html", form=form, team=team_data)
