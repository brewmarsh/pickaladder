<<<<<<< HEAD
from flask import render_template
from . import bp

@bp.route("/", methods=["GET"])
def index():
    return render_template("marketplace/index.html")
=======
"""Routes for the marketplace blueprint."""

from __future__ import annotations

from firebase_admin import firestore
from flask import Response, flash, g, redirect, render_template, request, url_for

from pickaladder.auth.decorators import login_required
from pickaladder.group.services.group_service import GroupService
from pickaladder.season.services import SeasonService

from . import bp
from .repository import MarketplaceRepository


@bp.route("/", methods=["GET"])
@login_required
def view_marketplace() -> str:
    """Display the marketplace landing page."""
    db = firestore.client()
    search_term = request.args.get("search")
    search_type = request.args.get("type", "all")
    sort = request.args.get("sort", "popular")

    featured_groups = MarketplaceRepository.get_featured_groups(db)

    # In a real app, search_marketplace would handle search_type
    results = MarketplaceRepository.search_marketplace(
        db, query_text=search_term, filters={"sort": sort, "type": search_type}
    )

    return render_template(
        "marketplace/index.html",
        featured_groups=featured_groups,
        results=results,
        search_term=search_term,
        search_type=search_type,
        sort=sort,
    )


@bp.route("/join-division/<season_id>/<int:division_index>", methods=["POST"])
@login_required
def join_division(season_id: str, division_index: int) -> Response:
    """Handle join requests for public divisions."""
    db = firestore.client()
    user_id = g.user["id"]

    season = SeasonService.get_season(db, season_id)
    if not season:
        flash("Season not found.", "danger")
        return redirect(url_for("marketplace.view_marketplace"))

    divisions = season.get("divisions", [])
    if division_index >= len(divisions):
        flash("Invalid division.", "danger")
        return redirect(url_for("marketplace.view_marketplace"))

    division = divisions[division_index]

    # Check join policy
    if division.get("join_policy") == "OPEN":
        try:
            SeasonService.join_season_division(db, season_id, division_index, user_id)
            flash(f"Successfully joined {division.get('name')}!", "success")
            return redirect(url_for("season.view_season", season_id=season_id))
        except Exception as e:
            flash(f"Error joining division: {e}", "danger")
            return redirect(url_for("marketplace.view_marketplace"))

    elif division.get("join_policy") == "REQUEST":
        group_id = season.get("groupId")
        try:
            GroupService.create_membership_request(
                db,
                group_id,
                user_id,
                f"Request to join division: {division.get('name')}",
            )
            flash("Membership request sent to the group owner.", "info")
        except ValueError as e:
            flash(str(e), "warning")

        return redirect(url_for("marketplace.view_marketplace"))
    else:
        flash("This division is invite-only.", "warning")
        return redirect(url_for("marketplace.view_marketplace"))
>>>>>>> 395736a075685dfc196237a25821dffdb0346839
