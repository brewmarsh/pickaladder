"""Tests for the ChallengeService."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from google.cloud.firestore_v1.client import Client
from google.cloud.firestore_v1.transaction import Transaction

from pickaladder.match.services.challenge_service import ChallengeService


@pytest.fixture
def mock_db() -> MagicMock:
    """Mock Firestore Client."""
    db = MagicMock(spec=Client)
    db.transaction.return_value = MagicMock(spec=Transaction)
    return db


@patch(
    "pickaladder.match.services.challenge_service.SocialCreditService.adjust_balance"
)
def test_issue_challenge_success(
    mock_adjust_balance: MagicMock, mock_db: MagicMock
) -> None:
    """Test successful issuance of a challenge."""
    mock_db.collection.return_value.where.return_value.where.return_value.get.return_value = []

    mock_doc_ref = MagicMock()
    mock_doc_ref.id = "challenge_123"
    mock_db.collection.return_value.document.return_value = mock_doc_ref

    # We need to simulate the transactional decorator
    with patch("firebase_admin.firestore.transactional", lambda f: f):
        challenge_id = ChallengeService.issue_challenge(mock_db, "userA", "userB", 10)

    assert challenge_id == "challenge_123"
    mock_adjust_balance.assert_called_once_with(
        mock_db, mock_db.transaction(), "userA", -10
    )
    mock_db.transaction().set.assert_called_once()


def test_issue_challenge_self(mock_db: MagicMock) -> None:
    """Test cannot challenge oneself."""
    with pytest.raises(ValueError, match="cannot challenge yourself"):
        ChallengeService.issue_challenge(mock_db, "userA", "userA", 10)


def test_issue_challenge_negative_wager(mock_db: MagicMock) -> None:
    """Test wager must be non-negative."""
    with pytest.raises(ValueError, match="non-negative"):
        ChallengeService.issue_challenge(mock_db, "userA", "userB", -5)


def test_issue_challenge_exceeds_max_wager(mock_db: MagicMock) -> None:
    """Test wager cannot exceed MAX_WAGER."""
    with pytest.raises(ValueError, match="exceed"):
        ChallengeService.issue_challenge(
            mock_db, "userA", "userB", ChallengeService.MAX_WAGER + 1
        )


@patch(
    "pickaladder.match.services.challenge_service.SocialCreditService.adjust_balance"
)
def test_accept_challenge_success(
    mock_adjust_balance: MagicMock, mock_db: MagicMock
) -> None:
    """Test successful acceptance of a challenge."""
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
        "challenged_id": "userB",
        "status": "pending",
        "wager_amount": 10,
        "expires_at": None,  # Simplify test, normally would check expiration
    }
    mock_db.collection.return_value.document.return_value.get.return_value = mock_doc

    with patch("firebase_admin.firestore.transactional", lambda f: f):
        ChallengeService.accept_challenge(mock_db, "challenge_123", "userB")

    mock_adjust_balance.assert_called_once_with(
        mock_db, mock_db.transaction(), "userB", -10
    )
    mock_db.transaction().update.assert_called_once()
    update_call = mock_db.transaction().update.call_args[0][1]
    assert update_call["status"] == "accepted"


def test_accept_challenge_wrong_user(mock_db: MagicMock) -> None:
    """Test only challenged user can accept."""
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {"challenged_id": "userB", "status": "pending"}
    mock_db.collection.return_value.document.return_value.get.return_value = mock_doc

    with patch("firebase_admin.firestore.transactional", lambda f: f):
        with pytest.raises(ValueError, match="can accept"):
            ChallengeService.accept_challenge(mock_db, "challenge_123", "userA")


@patch(
    "pickaladder.match.services.challenge_service.SocialCreditService.adjust_balance"
)
def test_decline_challenge_success(
    mock_adjust_balance: MagicMock, mock_db: MagicMock
) -> None:
    """Test successful declining of a challenge."""
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
        "challenger_id": "userA",
        "challenged_id": "userB",
        "status": "pending",
        "wager_amount": 15,
    }
    mock_db.collection.return_value.document.return_value.get.return_value = mock_doc

    with patch("firebase_admin.firestore.transactional", lambda f: f):
        ChallengeService.decline_challenge(mock_db, "challenge_123", "userB")

    mock_adjust_balance.assert_called_once_with(
        mock_db, mock_db.transaction(), "userA", 15
    )
    mock_db.transaction().update.assert_called_once()
    update_call = mock_db.transaction().update.call_args[0][1]
    assert update_call["status"] == "declined"
