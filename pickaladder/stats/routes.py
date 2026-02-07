from __future__ import annotations

from typing import Any

from firebase_admin import firestore
from flask import jsonify, request

from pickaladder.auth.decorators import login_required

from . import bp
from .services import PredictionService


@bp.route("/prediction", methods=["GET"])
@login_required
def get_prediction() -> Any:
    """Endpoint to get a match prediction."""
    team1_id_str = request.args.get("team1_id", "")
    team2_id_str = request.args.get("team2_id", "")

    if not team1_id_str or not team2_id_str:
        return (
            jsonify({"error": "Missing team1_id or team2_id parameters"}),
            400,
        )

    team1_ids = [uid.strip() for uid in team1_id_str.split(",") if uid.strip()]
    team2_ids = [uid.strip() for uid in team2_id_str.split(",") if uid.strip()]

    if not team1_ids or not team2_ids:
        return jsonify({"error": "Invalid team IDs"}), 400

    db = firestore.client()
    prediction = PredictionService.predict_matchup(db, team1_ids, team2_ids)

    return jsonify(prediction)
