"""End-to-end integration tests for the session-first workflow."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from firebase_admin import firestore

from pickaladder.group.services.session_service import SessionService
from pickaladder.match.models import MatchSubmission
from pickaladder.match.services.command import MatchCommandService


def test_complete_session_lifecycle(mock_db, mock_db_write):
    """Test session creation, match recording, and batch verification."""
    from pickaladder import create_app

    app = create_app({"TESTING": True, "WTF_CSRF_ENABLED": False})

    with app.app_context():
        db = firestore.client()

        # Simple manual batch mock
        class MockBatch:
            def __init__(self):
                self.ops = []

            def set(self, ref, data):
                self.ops.append(("set", ref, data))

            def update(self, ref, data):
                self.ops.append(("update", ref, data))

            def commit(self):
                for op, ref, data in self.ops:
                    if op == "set":
                        ref.set(data)
                    elif op == "update":
                        ref.update(data)

        if not hasattr(db, "batch"):
            db.batch = MagicMock(side_effect=MockBatch)

        # 0. Setup mock group and players
        group_id = "test_group"
        player_ids = ["u1", "u2", "u3", "u4"]
        player_refs = [db.collection("users").document(pid) for pid in player_ids]

        db.collection("groups").document(group_id).set(
            {"name": "Test Group", "members": player_refs}
        )

        BASE_ELO = 1200
        for pid in player_ids:
            db.collection("users").document(pid).set(
                {
                    "username": f"user_{pid}",
                    "email": f"{pid}@test.com",
                    "stats": {"wins": 0, "losses": 0, "elo": BASE_ELO},
                }
            )

        # 1. Create a session
        creator_id = "u1"

        session_id = SessionService.create_session(db, group_id, creator_id, player_ids)
        assert session_id is not None

        # 2. Record multiple matches via the session
        match_ids = []
        NUM_MATCHES = 2

        # Mock build match result to avoid url_for
        with patch(
            "pickaladder.match.services.command.MatchCommandService._build_match_result"
        ) as mock_build:
            mock_build.side_effect = lambda mid, data: MagicMock(id=mid)

            for _ in range(NUM_MATCHES):
                sub = MatchSubmission(
                    match_type="doubles",
                    player_1_id="u1",
                    player_2_id="u3",
                    partner_id="u2",
                    opponent_2_id="u4",
                    score_p1=11,
                    score_p2=5,
                    match_date=datetime.now(timezone.utc),
                    group_id=group_id,
                    created_by=creator_id,
                )
                res = MatchCommandService.record_match(
                    db, sub, current_user={"uid": creator_id}, session_id=session_id
                )
                match_ids.append(res.id)
                SessionService.add_match_to_session(db, session_id, res.id)
    # Verify matches are linked
    session_data = SessionService.get_session(db, session_id)
    assert len(session_data["matchIds"]) == NUM_MATCHES

    # 3. Perform batch verification (Threshold 2)
    # First approval
    success = SessionService.verify_session(db, session_id, "u1")
    assert success is True
    session_data = SessionService.get_session(db, session_id)
    assert session_data["status"] == "ACTIVE"

    # Second approval (should trigger completion)
    success = SessionService.verify_session(db, session_id, "u2")
    assert success is True

    # 4. Verify results
    # Check session status
    session_final = SessionService.get_session(db, session_id)
    assert session_final["status"] == "COMPLETED"
    NUM_VERIFICATIONS = 2
    assert len(session_final["verifiedBy"]) == NUM_VERIFICATIONS
    # Check match statuses
    for mid in match_ids:
        match_doc = db.collection("matches").document(mid).get().to_dict()
        assert match_doc["is_verified"] is True
