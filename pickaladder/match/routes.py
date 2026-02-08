"""Routes for the match blueprint."""

from __future__ import annotations

import datetime
from typing import Any

from firebase_admin import firestore
from flask import flash, g, jsonify, redirect, render_template, request, url_for

from pickaladder.auth.decorators import login_required

from . import bp
from .forms import MatchForm
from .services import MatchService


# TODO: Add type hints for Agent clarity
@bp.route("/<string:match_id>")
@login_required
def view_match_page(match_id: str) -> Any:
    """Display the details of a single match."""
    db = firestore.client()
    match_data = MatchService.get_match_by_id(db, match_id)
    if not match_data:
        flash("Match not found.", "danger")
        return redirect(url_for("user.dashboard"))

    match_type = match_data.get("matchType", "singles")

    context = {"match": match_data, "match_type": match_type}

    if match_type == "doubles":
        # Fetch team members
        # team1 and team2 are lists of refs
        team1_refs = match_data.get("team1", [])
        team2_refs = match_data.get("team2", [])

        team1_data = []
        for ref in team1_refs:
            p = ref.get()
            if p.exists:
                team1_data.append(p.to_dict())

        team2_data = []
        for ref in team2_refs:
            p = ref.get()
            if p.exists:
                team2_data.append(p.to_dict())

        context["team1"] = team1_data
        context["team2"] = team2_data

    else:
        # Fetch player data from references
        # Handle cases where refs might be missing in corrupted data
        player1_ref = match_data.get("player1Ref")
        player2_ref = match_data.get("player2Ref")

        player1_data = {}
        player2_data = {}
        player1_record = {"wins": 0, "losses": 0}
        player2_record = {"wins": 0, "losses": 0}

        if player1_ref:
            player1 = player1_ref.get()
            if player1.exists:
                player1_data = player1.to_dict()
                player1_record = MatchService.get_player_record(db, player1_ref)

        if player2_ref:
            player2 = player2_ref.get()
            if player2.exists:
                player2_data = player2.to_dict()
                player2_record = MatchService.get_player_record(db, player2_ref)

        context.update(
            {
                "player1": player1_data,
                "player2": player2_data,
                "player1_record": player1_record,
                "player2_record": player2_record,
            }
        )

    return render_template("view_match.html", **context)


# TODO: Add type hints for Agent clarity
@bp.route("/record", methods=["GET", "POST"])
@login_required
def record_match() -> Any:
    """Handle match recording for both web form and optimistic JSON submission."""
    db = firestore.client()
    user_id = g.user["uid"]
    group_id = request.args.get("group_id")
    tournament_id = request.args.get("tournament_id")
    candidate_player_ids = MatchService.get_candidate_player_ids(
        db, user_id, group_id, tournament_id
    )

    tournament_name = None
    if tournament_id:
        tournament_doc = db.collection("tournaments").document(tournament_id).get()
        if tournament_doc.exists:
            tournament_name = tournament_doc.to_dict().get("name")

    if request.method == "POST" and request.is_json:
        data = request.get_json()
        form = MatchForm(data=data)

        # Security check: Ensure all selected players are valid candidates
        selected_players: set[str | None] = {data.get("player2")}
        if data.get("match_type") == "doubles":
            selected_players.add(data.get("partner"))
            selected_players.add(data.get("opponent2"))

        if not all(
            p in candidate_player_ids for p in selected_players if p is not None
        ):
            return (
                jsonify({"status": "error", "message": "Invalid opponent selected."}),
                403,
            )

        # Populate choices for validation to work
        choices: list[tuple[str, str]] = [(p_id, "") for p_id in candidate_player_ids]
        form.player1.choices = choices  # type: ignore[assignment]
        form.player2.choices = choices  # type: ignore[assignment]
        if data.get("match_type") == "doubles":
            form.partner.choices = choices  # type: ignore[assignment]
            form.opponent2.choices = choices  # type: ignore[assignment]

        if form.validate():
            try:
                json_group_id = data.get("group_id") or group_id
                json_tournament_id = data.get("tournament_id") or tournament_id
                MatchService.save_match_data(
                    db, user_id, data, json_group_id, json_tournament_id
                )
                return jsonify({"status": "success", "message": "Match recorded."}), 200
            except Exception as e:
                return jsonify({"status": "error", "message": str(e)}), 500
        else:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "Validation failed",
                        "errors": form.errors,
                    }
                ),
                400,
            )

    # Standard GET request or form submission
    form = MatchForm()

    # Fetch and populate player choices for the form dropdowns
    player1_candidate_ids = MatchService.get_candidate_player_ids(
        db, user_id, group_id, tournament_id, include_user=True
    )

    player1_choices = []
    if player1_candidate_ids:
        candidate_refs = [
            db.collection("users").document(uid) for uid in player1_candidate_ids
        ]
        users = db.get_all(candidate_refs)
        for user_doc in users:
            if user_doc.exists:
                player1_choices.append(
                    (user_doc.id, user_doc.to_dict().get("name", user_doc.id))
                )

    form.player1.choices = player1_choices  # type: ignore[assignment]

    player_choices = []
    if candidate_player_ids:
        # Batch fetch user data for choices
        candidate_refs = [
            db.collection("users").document(uid) for uid in candidate_player_ids
        ]
        users = db.get_all(candidate_refs)
        for user_doc in users:
            if user_doc.exists:
                player_choices.append(
                    (user_doc.id, user_doc.to_dict().get("name", user_doc.id))
                )

    form.player2.choices = player_choices  # type: ignore[assignment]
    form.partner.choices = player_choices  # type: ignore[assignment]
    form.opponent2.choices = player_choices  # type: ignore[assignment]

    if request.method == "GET":
        form.player1.data = user_id
        form.group_id.data = group_id
        form.tournament_id.data = tournament_id
        opponent_id = request.args.get("opponent")
        if opponent_id:
            form.player2.data = opponent_id
        user_ref = db.collection("users").document(user_id)
        user_snapshot = user_ref.get()
        if user_snapshot.exists:
            user_data = user_snapshot.to_dict()
            last_match_type = user_data.get("lastMatchRecordedType")
            if last_match_type:
                form.match_type.data = last_match_type

    if form.validate_on_submit():
        player_1_id = request.form.get("player1") or user_id
        group_id = form.group_id.data or group_id
        tournament_id = form.tournament_id.data or tournament_id

        # Uniqueness check
        player_ids = [player_1_id, form.player2.data]
        if form.match_type.data == "doubles":
            player_ids.extend([form.partner.data, form.opponent2.data])

        # Filter out empty values and check for duplicates
        active_players = [p for p in player_ids if p]
        if len(active_players) != len(set(active_players)):
            flash("All players must be unique.", "danger")
            return render_template(
                "record_match.html",
                form=form,
                group_id=group_id,
                tournament_id=tournament_id,
                tournament_name=tournament_name,
            )

        try:
            MatchService.save_match_data(db, player_1_id, form, group_id, tournament_id)
            flash("Match recorded successfully.", "success")
            if tournament_id:
                return redirect(
                    url_for("tournament.view_tournament", tournament_id=tournament_id)
                )
            if group_id:
                return redirect(url_for("group.view_group", group_id=group_id))
            return redirect(url_for("user.dashboard"))
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")

    return render_template(
        "record_match.html",
        form=form,
        group_id=group_id,
        tournament_id=tournament_id,
        tournament_name=tournament_name,
    )


# TODO: Add type hints for Agent clarity
@bp.route("/leaderboard")
@login_required
def leaderboard() -> Any:
    """Display a global leaderboard.

    Note: This is a simplified, non-scalable implementation. A production-ready
    leaderboard on Firestore would likely require denormalization and Cloud Functions.
    """
    db = firestore.client()
    try:
        players = MatchService.get_leaderboard_data(db)
    except Exception as e:
        players = []
        flash(f"An error occurred while fetching the leaderboard: {e}", "danger")

    latest_matches = MatchService.get_latest_matches(db)

    return render_template(
        "leaderboard.html",
        players=players,
        latest_matches=latest_matches,
        current_user_id=g.user["uid"],
    )
