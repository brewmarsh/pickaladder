"""Tests for DUPR rating synchronization."""

from unittest.mock import patch

import pytest

from pickaladder.user.services.profile import sync_dupr_rating


@pytest.fixture
def mock_dupr_api():
    # Use fetch_rating instead of get_rating
    with patch(
        "pickaladder.user.services.dupr_service.DUPRService.fetch_rating",
    ) as mock:
        yield mock


def test_sync_dupr_rating_updates_user(mock_db, mock_dupr_api) -> None:
    """Verify that sync_dupr_rating fetches from API and updates Firestore."""
    user_id = "test_user"
    dupr_id = "DUPR123"
    mock_db.collection("users").document(user_id).set(
        {"dupr_id": dupr_id, "dupr_rating": 3.5},
    )

    EXPECTED_RATING = 4.2
    mock_dupr_api.return_value = EXPECTED_RATING

    success = sync_dupr_rating(mock_db, user_id)

    assert success is True
    updated_user = mock_db.collection("users").document(user_id).get().to_dict()
    assert updated_user["dupr_rating"] == EXPECTED_RATING
    assert updated_user["duprRating"] == EXPECTED_RATING


def test_sync_dupr_rating_no_id(mock_db, mock_dupr_api) -> None:
    """Verify that sync fails if user has no DUPR ID."""
    user_id = "no_id_user"
    mock_db.collection("users").document(user_id).set({"email": "test@test.com"})

    success = sync_dupr_rating(mock_db, user_id)
    assert success is False
