"""Tests for DUPR rating synchronization."""

import pytest
from unittest.mock import MagicMock, patch
from pickaladder.user.services.profile import sync_dupr_rating

@pytest.fixture
def mock_dupr_api():
    # Use fetch_rating instead of get_rating
    with patch("pickaladder.user.services.dupr_service.DUPRService.fetch_rating") as mock:
        yield mock

def test_sync_dupr_rating_updates_user(mock_db, mock_dupr_api):
    """Verify that sync_dupr_rating fetches from API and updates Firestore."""
    user_id = "test_user"
    dupr_id = "DUPR123"
    mock_db.collection("users").document(user_id).set({
        "dupr_id": dupr_id,
        "dupr_rating": 3.5
    })
    
    mock_dupr_api.return_value = 4.2
    
    success = sync_dupr_rating(mock_db, user_id)
    
    assert success is True
    updated_user = mock_db.collection("users").document(user_id).get().to_dict()
    assert updated_user["dupr_rating"] == 4.2
    assert updated_user["duprRating"] == 4.2

def test_sync_dupr_rating_no_id(mock_db, mock_dupr_api):
    """Verify that sync fails if user has no DUPR ID."""
    user_id = "no_id_user"
    mock_db.collection("users").document(user_id).set({"email": "test@test.com"})
    
    success = sync_dupr_rating(mock_db, user_id)
    assert success is False
