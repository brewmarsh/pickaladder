"""Routes for the tournament blueprint."""

from __future__ import annotations

from typing import Any

from firebase_admin import firestore
from flask import (
    flash,
    g,
    current_app,
    redirect,
    render_template,
    request,
    url_for,
)

from pickaladder.auth.decorators import login_required
from pickaladder.user.utils import UserService, smart_display_name

from . import bp
from .forms import InvitePlayerForm, TournamentForm


def _get_tournament_standings(
    db: Any, tournament_id: str, match_type: str
) -> list[dict[str, Any]]:
    """Calculate tournament standings based on matches."""
    matches_query = (
        db.collection("matches")
        .where(filter=firestore.FieldFilter("tournamentId", "==", tournament_id))
        .stream()
    )
    standings: dict[str, dict[str, Any]] = {}

    for match in matches_query:
        data = match.to_dict()
        p1_score = data.get("player1Score", 0)
        p2_score = data.get("player2Score", 0)

        if match_type == "doubles":
            team1_id = data.get("team1Id")
            team2_id = data.get("team2Id")
            if not team1_id or not team2_id:
                continue

            if team1_id not in standings:
                standings[team1_id] = {
                    "id": team1_id,
                    "wins": 0,
                    "losses": 0,
                    "name": "Unknown Team",
                }
            if team2_id not in standings:
                standings[team2_id] = {
                    "id": team2_id,
                    "wins": 0,
                    "losses": 0,
                    "name": "Unknown Team",
                }

            if p1_score > p2_score:
                standings[team1_id]["wins"] += 1
                standings[team2_id]["losses"] += 1
            else:
                standings[team2_id]["wins"] += 1
                standings[team1_id]["losses"] += 1
        else:
            p1_ref = data.get("player1Ref")
            p2_ref = data.get("player2Ref")
            if not p1_ref or not p2_ref:
                continue

            p1_id = p1_ref.id
            p2_id = p2_ref.id

            if p1_id not in standings:
                standings[p1_id] = {"id": p1_id, "wins": 0, "losses": 0}
            if p2_id not in standings:
                standings[p2_id] = {"id": p2_id, "wins": 0, "losses": 0}

            if p1_score > p2_score:
                standings[p1_id]["wins"] += 1
                standings[p2_id]["losses"] += 1
            else:
                standings[p2_id]["wins"] += 1
                standings[p1_id]["losses"] += 1

    standings_list = list(standings.values())
    if not standings_list:
        return []

    if match_type == "doubles":
        for s in standings_list:
            team_doc = db.collection("teams").document(s["id"]).get()
            if team_doc.exists:
                s["name"] = team_doc.to_dict().get("name", "Unknown Team")
    else:
        user_ids = [s["id"] for s in standings_list]
        user_refs = [db.collection("users").document(uid) for uid in user_ids]
        user_docs = db.get_all(user_refs)
        users_map = {doc.id: doc.to_dict() for doc in user_docs if doc.exists}
        for s in standings_list:
            user_data = users_map.get(s["id"], {})
            s["name"] = (
                user_data.get("name") or user_data.get("username") or "Unknown Player"
            )

    standings_list.sort(key=lambda x: (x["wins"], -x["losses"]), reverse=True)
    return standings_list


@bp.route("/", methods=["GET"])
@login_required
def list_tournaments() -> Any:
    """List all tournaments."""
    db = firestore.client()
    user_ref = db.collection("users").document(g.user["uid"])

    # Fetch tournaments where the user is an owner or participant
    # Note: Firestore 'array-contains' might be tricky with objects in arrays.
    # Usually, it's better to store participant IDs in a separate array for querying.
    # But for now, let's fetch all and filter, or just fetch all public ones if
    # they existed. User specifically said: "stores them in a participants array
    # with a 'pending' status" To query efficiently, we might need a separate
    # 'participant_ids' array.

    # For now, let's fetch tournaments where ownerRef is the user
    owned_tournaments = (
        db.collection("tournaments").where("ownerRef", "==", user_ref).stream()
    )

    # And tournaments where user is a participant.
    # Since we store objects in 'participants', we can't use 'array-contains' on the
    # object unless we know the exact object.
    # Let's also maintain a 'participant_ids' array for easier querying.
    participating_tournaments = (
        db.collection("tournaments")
        .where("participant_ids", "array_contains", g.user["uid"])
        .stream()
    )

    tournaments = []
    seen_ids = set()

    for doc in owned_tournaments:
        data = doc.to_dict()
        data["id"] = doc.id
        tournaments.append(data)
        seen_ids.add(doc.id)

    for doc in participating_tournaments:
        if doc.id not in seen_ids:
            data = doc.to_dict()
            data["id"] = doc.id
            tournaments.append(data)
            seen_ids.add(doc.id)

    return render_template("tournaments.html", tournaments=tournaments)


@bp.route("/create", methods=["GET", "POST"])
@login_required
def create_tournament() -> Any:
    """Create a new tournament."""
    form = TournamentForm()
    if form.validate_on_submit():
        db = firestore.client()
        user_ref = db.collection("users").document(g.user["uid"])
        try:
            tournament_data = {
                "name": form.name.data,
                "date": str(form.date.data),
                "location": form.location.data,
                "matchType": form.match_type.data,
                "ownerRef": user_ref,
                "participants": [{"userRef": user_ref, "status": "accepted"}],
                "participant_ids": [g.user["uid"]],
                "createdAt": firestore.SERVER_TIMESTAMP,
            }
            _, new_tournament_ref = db.collection("tournaments").add(tournament_data)
            flash("Tournament created successfully.", "success")
            return redirect(
                url_for(".view_tournament", tournament_id=new_tournament_ref.id)
            )
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")

    return render_template("create_tournament.html", form=form)


@bp.route("/<string:tournament_id>", methods=["GET", "POST"])
@login_required
def view_tournament(tournament_id: str) -> Any:
    """View a single tournament."""
    db = firestore.client()
    tournament_ref = db.collection("tournaments").document(tournament_id)
    tournament_doc = tournament_ref.get()

    if not tournament_doc.exists:
        flash("Tournament not found.", "danger")
        return redirect(url_for(".list_tournaments"))

    tournament_data = tournament_doc.to_dict()
    tournament_data["id"] = tournament_doc.id
    match_type = tournament_data.get("matchType", "singles")
    status = tournament_data.get("status", "Active")

    # Fetch participant data
    participants = []
    participant_objs = tournament_data.get("participants", [])
    if participant_objs:
        user_refs = [obj["userRef"] for obj in participant_objs]
        user_docs = db.get_all(user_refs)
        users_map = {
            doc.id: {**doc.to_dict(), "id": doc.id} for doc in user_docs if doc.exists
        }

        for obj in participant_objs:
            user_id = obj["userRef"].id
            if user_id in users_map:
                user_data = users_map[user_id]
                participants.append(
                    {
                        "user": user_data,
                        "status": obj["status"],
                        "display_name": smart_display_name(user_data),
                    }
                )

    # Calculate Standings
    standings = _get_tournament_standings(db, tournament_id, match_type)
    podium = standings[:3] if status == "Completed" else []

    # Invite form
    invite_form = InvitePlayerForm()
    # Populate choices with friends not in the tournament
    friends = UserService.get_user_friends(db, g.user["uid"])
    participant_ids = {obj["userRef"].id for obj in participant_objs}

    eligible_friends = [f for f in friends if f["id"] not in participant_ids]
    invite_form.player.choices = [
        (f["id"], f.get("name") or f["id"]) for f in eligible_friends
    ]

    if invite_form.validate_on_submit() and "player" in request.form:
        invited_user_id = invite_form.player.data
        invited_user_ref = db.collection("users").document(invited_user_id)

        try:
            tournament_ref.update(
                {
                    "participants": firestore.ArrayUnion(
                        [{"userRef": invited_user_ref, "status": "pending"}]
                    ),
                    "participant_ids": firestore.ArrayUnion([invited_user_id]),
                }
            )
            flash("Player invited successfully.", "success")
            return redirect(url_for(".view_tournament", tournament_id=tournament_id))
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", "danger")

    return render_template(
        "tournament/view.html",
        tournament=tournament_data,
        participants=participants,
        standings=standings,
        podium=podium,
        invite_form=invite_form,
        is_owner=(tournament_data.get("ownerRef").id == g.user["uid"]),
    )


@bp.route("/<string:tournament_id>/complete", methods=["POST"])
@login_required
def complete_tournament(tournament_id: str) -> Any:
    """Mark a tournament as completed and notify participants."""
    db = firestore.client()
    tournament_ref = db.collection("tournaments").document(tournament_id)
    tournament_doc = tournament_ref.get()

    if not tournament_doc.exists:
        flash("Tournament not found.", "danger")
        return redirect(url_for(".list_tournaments"))

    tournament_data = tournament_doc.to_dict()
    if tournament_data.get("ownerRef").id != g.user["uid"]:
        flash("Only the owner can complete the tournament.", "danger")
        return redirect(url_for(".view_tournament", tournament_id=tournament_id))

    try:
        tournament_ref.update({"status": "Completed"})

        # Calculate final standings for the email
        match_type = tournament_data.get("matchType", "singles")
        standings = _get_tournament_standings(db, tournament_id, match_type)
        winner_name = standings[0]["name"] if standings else "No one"

        # Send emails to all participants
        participants = tournament_data.get("participants", [])
        user_refs = [p["userRef"] for p in participants if p["status"] == "accepted"]
        if user_refs:
            user_docs = db.get_all(user_refs)
            for user_doc in user_docs:
                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    email = user_data.get("email")
                    if email:
                        try:
                            from pickaladder.utils import send_email

                            send_email(
                                to=email,
                                subject=f"The results are in for {tournament_data['name']}!",
                                template="email/tournament_results.html",
                                user=user_data,
                                tournament=tournament_data,
                                winner_name=winner_name,
                                standings=standings[:3],
                            )
                        except Exception as e:
                            current_app.logger.error(
                                f"Failed to send tournament results email to {email}: {e}"
                            )

        flash("Tournament completed and results sent!", "success")
    except Exception as e:
        flash(f"An error occurred: {e}", "danger")

    return redirect(url_for(".view_tournament", tournament_id=tournament_id))


@bp.route("/<string:tournament_id>/join", methods=["POST"])
@login_required
def join_tournament(tournament_id: str) -> Any:
    """Accept an invite to a tournament."""
    db = firestore.client()
    tournament_ref = db.collection("tournaments").document(tournament_id)
    tournament_doc = tournament_ref.get()

    if not tournament_doc.exists:
        flash("Tournament not found.", "danger")
        return redirect(url_for(".list_tournaments"))

    tournament_data = tournament_doc.to_dict()
    participants = tournament_data.get("participants", [])

    updated = False
    for p in participants:
        if p["userRef"].id == g.user["uid"] and p["status"] == "pending":
            p["status"] = "accepted"
            updated = True
            break

    if updated:
        tournament_ref.update({"participants": participants})
        flash("You have joined the tournament!", "success")
    else:
        flash("No pending invitation found.", "warning")

    return redirect(url_for(".view_tournament", tournament_id=tournament_id))
