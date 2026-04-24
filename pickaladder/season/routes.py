"""Routes for the season blueprint."""

from __future__ import annotations

from typing import Any

from firebase_admin import firestore
from flask import flash, g, redirect, render_template, request, url_for

from pickaladder.auth.decorators import login_required
from pickaladder.constants.messages import COMMON_MESSAGES, GROUP_MESSAGES
from pickaladder.core.activity.models import ActivityType
from pickaladder.core.activity.services import ActivityService
from pickaladder.group.services.group_service import GroupService

from . import bp
from .forms import SeasonForm
from .services import SeasonFinalizationService, SeasonService, SeasonStandingsService


@bp.route("/<string:season_id>")
@login_required
def view_season(season_id: str) -> Any:
    """Display season standings."""
    db = firestore.client()
    season = SeasonService.get_season(db, season_id)
    if not season:
        flash("Season not found", "danger")
        return redirect(url_for("group.view_groups"))

    group_id = season["groupId"]
    try:
        group_context = GroupService.get_group_details(db, group_id, g.user.uid)
    except Exception:
        flash(GROUP_MESSAGES["NOT_FOUND"], "danger")
        return redirect(url_for("group.view_groups"))

    # If completed, we use the finalStandings snapshot
    if season.get("status") == "COMPLETED" and "finalStandings" in season:
        standings = season["finalStandings"]
    else:
        standings = SeasonStandingsService.get_season_standings(db, season_id)

    return render_template(
        "season/view.html",
        group=group_context["group"],
        season=season,
        standings=standings,
        is_admin=group_context["is_admin"],
    )


@bp.route("/group/<string:group_id>")
@login_required
def list_seasons(group_id: str) -> Any:
    """List all seasons for a group."""
    db = firestore.client()
    try:
        group_context = GroupService.get_group_details(db, group_id, g.user.uid)
    except Exception:
        flash(GROUP_MESSAGES["NOT_FOUND"], "danger")
        return redirect(url_for("group.view_groups"))

    seasons = SeasonService.get_seasons_for_group(db, group_id)
    return render_template(
        "season/list.html",
        group=group_context["group"],
        seasons=seasons,
        is_admin=group_context["is_admin"],
    )


@bp.route("/group/<string:group_id>/create", methods=["GET", "POST"])
@login_required
def create_season(group_id: str) -> Any:
    """Create a new season for a group."""
    db = firestore.client()
    try:
        group_context = GroupService.get_group_details(db, group_id, g.user.uid)
        if not group_context["is_admin"]:
            flash(GROUP_MESSAGES["ACCESS_DENIED"], "danger")
            return redirect(url_for("group.view_group", group_id=group_id))
    except Exception:
        flash(GROUP_MESSAGES["NOT_FOUND"], "danger")
        return redirect(url_for("group.view_groups"))

    form = SeasonForm()
    if form.validate_on_submit():
        try:
            season_data = {
                "name": form.name.data,
                "groupId": group_id,
                "startDate": form.start_date.data,
                "endDate": form.end_date.data,
                "status": form.status.data,
                "movementRules": {
                    "promotionCount": form.promotion_count.data,
                    "relegationCount": form.relegation_count.data,
                },
                "divisionIds": [],
            }
            SeasonService.create_season(db, season_data)
            flash("Season created successfully!", "success")
            return redirect(url_for(".list_seasons", group_id=group_id))
        except Exception as e:
            flash(COMMON_MESSAGES["UNEXPECTED_ERROR"].format(error=e), "danger")

    return render_template(
        "season/create_edit.html",
        form=form,
        group=group_context["group"],
        title="Create Season",
    )


@bp.route("/<string:season_id>/edit", methods=["GET", "POST"])
@login_required
def edit_season(season_id: str) -> Any:
    """Edit an existing season."""
    db = firestore.client()
    season = SeasonService.get_season(db, season_id)
    if not season:
        flash("Season not found", "danger")
        return redirect(url_for("group.view_groups"))

    group_id = season["groupId"]
    try:
        group_context = GroupService.get_group_details(db, group_id, g.user.uid)
        if not group_context["is_admin"]:
            flash(GROUP_MESSAGES["ACCESS_DENIED"], "danger")
            return redirect(url_for(".list_seasons", group_id=group_id))
    except Exception:
        flash(GROUP_MESSAGES["NOT_FOUND"], "danger")
        return redirect(url_for("group.view_groups"))

    form = SeasonForm(data=season)
    # Map nested rules to flat form fields
    if request.method == "GET":
        rules = season.get("movementRules", {})
        form.promotion_count.data = rules.get("promotionCount", 0)
        form.relegation_count.data = rules.get("relegationCount", 0)

    if form.validate_on_submit():
        try:
            update_data = {
                "name": form.name.data,
                "startDate": form.start_date.data,
                "endDate": form.end_date.data,
                "status": form.status.data,
                "movementRules": {
                    "promotionCount": form.promotion_count.data,
                    "relegationCount": form.relegation_count.data,
                },
            }
            SeasonService.update_season(db, season_id, update_data)
            flash("Season updated successfully!", "success")
            return redirect(url_for(".list_seasons", group_id=group_id))
        except Exception as e:
            flash(COMMON_MESSAGES["UNEXPECTED_ERROR"].format(error=e), "danger")

    return render_template(
        "season/create_edit.html",
        form=form,
        group=group_context["group"],
        title="Edit Season",
        season_id=season_id,
    )


@bp.route("/<string:season_id>/finalize", methods=["GET", "POST"])
@login_required
def finalize_season(season_id: str) -> Any:
    """Preview and apply season finalization."""
    db = firestore.client()
    season = SeasonService.get_season(db, season_id)
    if not season:
        flash("Season not found", "danger")
        return redirect(url_for("group.view_groups"))

    group_id = season["groupId"]
    try:
        group_context = GroupService.get_group_details(db, group_id, g.user.uid)
        if not group_context["is_admin"]:
            flash(GROUP_MESSAGES["ACCESS_DENIED"], "danger")
            return redirect(url_for(".view_season", season_id=season_id))
    except Exception:
        flash(GROUP_MESSAGES["NOT_FOUND"], "danger")
        return redirect(url_for("group.view_groups"))

    if request.method == "POST":
        try:
            SeasonFinalizationService.finalize_season(db, season_id)

            # Log community activity
            ActivityService.log_activity(
                db,
                g.user.uid,
                ActivityType.SEASON_FINALIZED,
                {
                    "seasonId": season_id,
                    "seasonName": season.get("name")
                }
            )

            action = request.form.get("action", "finalize_only")
            if action == "start_next":
                # For now, we redirect to create page.
                # In a more advanced version, we'd pass the suggested participants via session or URL.
                flash("Season finalized! Create the next one below.", "success")
                return redirect(url_for(".create_season", group_id=group_id))

            flash("Season finalized and results captured!", "success")
            return redirect(url_for(".view_season", season_id=season_id))
        except Exception as e:
            flash(COMMON_MESSAGES["UNEXPECTED_ERROR"].format(error=e), "danger")

    movements = SeasonFinalizationService.calculate_movements(db, season_id)
    return render_template(
        "season/finalize.html",
        group=group_context["group"],
        season=season,
        movements=movements,
    )
