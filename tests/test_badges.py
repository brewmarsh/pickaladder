"""Tests for the Badge System."""

import pytest
from unittest.mock import MagicMock, patch
from pickaladder.badges.services import BadgeService
from pickaladder.badges.models import BADGES

@pytest.fixture
def mock_db():
    return MagicMock()

def test_award_badge_new(mock_db):
    user_id = "user123"
    badge_id = "ROOKIE"

    # Mock user document not having the badge
    mock_user_doc = MagicMock()
    mock_user_doc.exists = True
    mock_user_doc.to_dict.return_value = {"badges": []}
    mock_db.collection().document().get.return_value = mock_user_doc

    with patch("firebase_admin.firestore.ArrayUnion") as mock_union:
        result = BadgeService.award_badge(mock_db, user_id, badge_id)

    assert result is True
    mock_db.collection().document().update.assert_called_once()
    args, _ = mock_db.collection().document().update.call_args
    assert "badges" in args[0]

def test_award_badge_duplicate(mock_db):
    user_id = "user123"
    badge_id = "ROOKIE"

    # Mock user document already having the badge
    mock_user_doc = MagicMock()
    mock_user_doc.exists = True
    mock_user_doc.to_dict.return_value = {"badges": [{"badge_id": "ROOKIE"}]}
    mock_db.collection().document().get.return_value = mock_user_doc

    result = BadgeService.award_badge(mock_db, user_id, badge_id)

    assert result is False
    mock_db.collection().document().update.assert_not_called()

def test_evaluate_post_match_rookie(mock_db):
    user_id = "user123"

    # Mock stats showing 1st match
    with patch("pickaladder.badges.services.get_user_matches", return_value=[]), \
         patch("pickaladder.badges.services.calculate_stats", return_value={"total_games": 1}), \
         patch.object(BadgeService, "award_badge", return_value=True) as mock_award:

        awarded = BadgeService.evaluate_post_match(mock_db, user_id)

    assert "ROOKIE" in awarded
    mock_award.assert_any_call(mock_db, user_id, "ROOKIE")

def test_evaluate_post_match_hot_streak(mock_db):
    user_id = "user123"

    # Mock stats showing 3 wins in a row
    with patch("pickaladder.badges.services.get_user_matches", return_value=[]), \
         patch("pickaladder.badges.services.calculate_stats", return_value={"total_games": 5, "current_streak": 3, "streak_type": "W"}), \
         patch.object(BadgeService, "award_badge", return_value=True) as mock_award:

        awarded = BadgeService.evaluate_post_match(mock_db, user_id)

    assert "HOT_STREAK" in awarded
    mock_award.assert_any_call(mock_db, user_id, "HOT_STREAK")
