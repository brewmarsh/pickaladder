"""Tests for the SocialCreditService.
# ruff: noqa: PLR2004.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from google.cloud.firestore_v1.client import Client
from google.cloud.firestore_v1.transaction import Transaction

from pickaladder.user.services.credits import SocialCreditService


@pytest.fixture
def mock_db() -> MagicMock:
    """Mock Firestore Client."""
    return MagicMock(spec=Client)


@pytest.fixture
def mock_transaction() -> MagicMock:
    """Mock Firestore Transaction."""
    return MagicMock(spec=Transaction)


def test_get_balance_existing_user_with_credits(mock_db: MagicMock) -> None:
    """Test get_balance when user has a specific balance."""
    mock_doc = MagicMock()
    mock_doc.exists = True
    expected_balance = 250
    mock_doc.to_dict.return_value = {"social_credits": expected_balance}

    mock_db.collection.return_value.document.return_value.get.return_value = mock_doc

    balance = SocialCreditService.get_balance(mock_db, "user1")
    assert balance == expected_balance
    mock_db.collection.assert_called_with("users")
    mock_db.collection.return_value.document.assert_called_with("user1")


def test_get_balance_existing_user_no_credits(mock_db: MagicMock) -> None:
    """Test get_balance when user exists but hasn't had credits set yet."""
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {}

    mock_db.collection.return_value.document.return_value.get.return_value = mock_doc

    balance = SocialCreditService.get_balance(mock_db, "user2")
    assert balance == SocialCreditService.DEFAULT_BALANCE


def test_get_balance_user_not_found(mock_db: MagicMock) -> None:
    """Test get_balance when user does not exist."""
    mock_doc = MagicMock()
    mock_doc.exists = False

    mock_db.collection.return_value.document.return_value.get.return_value = mock_doc

    balance = SocialCreditService.get_balance(mock_db, "user3")
    assert balance == SocialCreditService.DEFAULT_BALANCE


def test_adjust_balance_success(
    mock_db: MagicMock,
    mock_transaction: MagicMock,
) -> None:
    """Test adjust_balance adds and returns correct balance."""
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {"social_credits": 100}

    user_ref_mock = MagicMock()
    user_ref_mock.get.return_value = mock_doc
    mock_db.collection.return_value.document.return_value = user_ref_mock

    adjust_amount = 50
    expected_balance = 150
    new_balance = SocialCreditService.adjust_balance(
        mock_db,
        mock_transaction,
        "user1",
        adjust_amount,
    )
    assert new_balance == expected_balance
    mock_transaction.update.assert_called_once_with(
        user_ref_mock,
        {"social_credits": expected_balance},
    )


def test_adjust_balance_insufficient_funds(
    mock_db: MagicMock,
    mock_transaction: MagicMock,
) -> None:
    """Test adjust_balance raises ValueError when delta results in negative balance."""
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {"social_credits": 10}

    user_ref_mock = MagicMock()
    user_ref_mock.get.return_value = mock_doc
    mock_db.collection.return_value.document.return_value = user_ref_mock

    with pytest.raises(ValueError, match="insufficient funds"):
        SocialCreditService.adjust_balance(mock_db, mock_transaction, "user1", -50)
    mock_transaction.update.assert_not_called()


def test_transfer_success(mock_db: MagicMock, mock_transaction: MagicMock) -> None:
    """Test successful transfer of social credits between users."""
    with pytest.MonkeyPatch.context() as m:
        adjust_mock = MagicMock()
        m.setattr(SocialCreditService, "adjust_balance", adjust_mock)

        transfer_amount = 25
        SocialCreditService.transfer(
            mock_db,
            mock_transaction,
            "userA",
            "userB",
            transfer_amount,
        )

        expected_calls = 2
        assert adjust_mock.call_count == expected_calls
        adjust_mock.assert_any_call(
            mock_db,
            mock_transaction,
            "userA",
            -transfer_amount,
        )
        adjust_mock.assert_any_call(mock_db, mock_transaction, "userB", transfer_amount)


def test_transfer_invalid_amount(
    mock_db: MagicMock,
    mock_transaction: MagicMock,
) -> None:
    """Test transfer raises ValueError when amount is non-positive."""
    with pytest.raises(ValueError, match="must be positive"):
        SocialCreditService.transfer(mock_db, mock_transaction, "userA", "userB", 0)
    with pytest.raises(ValueError, match="must be positive"):
        SocialCreditService.transfer(mock_db, mock_transaction, "userA", "userB", -10)
