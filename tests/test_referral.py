"""Tests for the referral system."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from flask import session
from mockfirestore import MockFirestore

# Mock user payloads
REFERRER_ID = "referrer_uid"
MOCK_PASSWORD = "Password123"  # nosec


@pytest.mark.usefixtures("apply_global_patches")
def test_capture_referrer_in_session(client: Any, mock_db: MockFirestore) -> None:
    """Test that the view_group route captures the referrer ID in the session."""
    # Setup user in mock firestore for before_request
    mock_db.collection("users").document("test_user_id").set(
        {"uid": "test_user_id", "username": "testuser"}
    )

    # Mock login
    with client.session_transaction() as sess:
        sess["user_id"] = "test_user_id"

    # Mock group details
    with patch("pickaladder.group.routes.GroupService.get_group_details") as mock_get:
        mock_owner_ref = MagicMock()
        mock_owner_ref.id = "admin"

        mock_get.return_value = {
            "group": {
                "id": "group1",
                "name": "Group 1",
                "ownerRef": mock_owner_ref,
            },
            "owner": {"username": "admin"},
            "eligible_friends": [],
            "leaderboard": [],
            "recent_matches": [],
            "best_buds": None,
            "team_leaderboard": [],
            "is_member": True,
            "members": [],
            "pending_members": [],
        }
        response = client.get("/group/group1?ref=" + REFERRER_ID)
        assert response.status_code == 200

        with client.session_transaction() as sess:
            assert sess.get("referrer_id") == REFERRER_ID


@pytest.mark.usefixtures("apply_global_patches")
def test_attribution_on_registration(client: Any, mock_db: MockFirestore) -> None:
    """Test that referral is attributed during registration."""
    # Setup referrer in Firestore
    mock_db.collection("users").document(REFERRER_ID).set({"username": "referrer"})

    # Set referrer in session
    with client.session_transaction() as sess:
        sess["referrer_id"] = REFERRER_ID

    # Mock user creation in Auth
    with (
        patch("firebase_admin.auth.create_user") as mock_create,
        patch("firebase_admin.auth.generate_email_verification_link") as mock_gen,
        patch("pickaladder.auth.routes.send_email"),
        patch("pickaladder.auth.routes.UserService.merge_ghost_user", return_value=False),
    ):
        mock_create.return_value = MagicMock(uid="new_user_uid")
        mock_gen.return_value = "http://verify"

        # Post registration with a very unique username
        response = client.post(
            "/auth/register",
            data={
                "username": "uniqueuser123",
                "email": "unique@example.com",
                "password": MOCK_PASSWORD,
                "confirm_password": MOCK_PASSWORD,
                "name": "New User",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200

        # If it failed, print the flash messages
        if b"Registration successful" not in response.data:
             print("DEBUG: Registration failed. Response data contains:")
             # Look for alert-danger
             import re
             errors = re.findall(r'class="alert alert-danger">(.*?)<', response.data.decode())
             print(f"DEBUG: Errors: {errors}")

        assert b"Registration successful" in response.data

    # Verify new user document has referred_by
    new_user_doc = mock_db.collection("users").document("new_user_uid").get().to_dict()
    assert new_user_doc is not None
    assert new_user_doc.get("referred_by") == REFERRER_ID

    # Verify session was cleared
    with client.session_transaction() as sess:
        assert sess.get("referrer_id") is None
