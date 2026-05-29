from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from pickaladder.match.services.challenge_service import ChallengeService


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_transaction():
    return MagicMock()


def test_issue_challenge_wager_limit(mock_db) -> None:
    """Test that challenges with wager > 50 are rejected."""
    with pytest.raises(ValueError, match="Wager cannot exceed 50 credits"):
        ChallengeService.issue_challenge(mock_db, "user1", "user2", 51)


def test_issue_challenge_active_limit(mock_db) -> None:
    """Test that users cannot have more than 3 active challenges."""
    # Mocking the query that checks for active challenges
    mock_query = MagicMock()
    mock_db.collection.return_value.where.return_value.where.return_value = mock_query

    # Simulate 3 active challenges
    mock_query.get.return_value = [MagicMock(), MagicMock(), MagicMock()]

    with pytest.raises(ValueError, match="You already have 3 active challenges"):
        ChallengeService.issue_challenge(mock_db, "user1", "user2", 10)


@patch("pickaladder.match.services.challenge_service.datetime")
def test_issue_challenge_expiration(mock_datetime, mock_db) -> None:
    """Test that challenges expire in 48 hours."""
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    mock_datetime.now.return_value = now
    mock_datetime.side_effect = datetime  # Allow normal datetime creation

    # We need to mock the transaction and the collection
    mock_tx = MagicMock()
    mock_db.transaction.return_value = mock_tx

    # Mock user document for SocialCreditService.adjust_balance
    mock_user_doc = MagicMock()
    mock_user_doc.exists = True
    mock_user_doc.to_dict.return_value = {"social_credits": 100}
    mock_db.collection.return_value.document.return_value.get.return_value = (
        mock_user_doc
    )

    with patch(
        "pickaladder.match.services.challenge_service.firestore",
    ) as mock_firestore:
        # mock_firestore.transactional is a decorator
        def side_effect(f):
            return f

        mock_firestore.transactional.side_effect = side_effect

        ChallengeService.issue_challenge(mock_db, "user1", "user2", 10)

        # Get the challenge_data from the set call
        args, _kwargs = mock_tx.set.call_args
        challenge_data = args[1]

        expected_expiry = now + timedelta(hours=48)
        assert challenge_data["expires_at"] == expected_expiry


def test_accept_challenge_expiration_check(mock_db) -> None:
    """Test that accepting an expired challenge fails and updates status."""
    challenge_id = "chal123"
    user_id = "user2"

    mock_tx = MagicMock()
    mock_db.transaction.return_value = mock_tx

    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {
        "challenged_id": user_id,
        "status": "pending",
        "wager_amount": 10,
        "expires_at": datetime.now(timezone.utc) - timedelta(hours=1),
    }

    with patch(
        "pickaladder.match.services.challenge_service.firestore",
    ) as mock_firestore:

        def side_effect(f):
            return f

        mock_firestore.transactional.side_effect = side_effect

        # Mocking the transaction.get
        mock_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_ref
        mock_ref.get.return_value = mock_doc

        with pytest.raises(ValueError, match="Challenge has expired"):
            ChallengeService.accept_challenge(mock_db, challenge_id, user_id)

        # Check if it updated the status to expired
        mock_tx.update.assert_any_call(mock_ref, {"status": "expired"})


if __name__ == "__main__":
    # Fallback to running tests manually if pytest environment is broken
    import unittest

    class TestChallengeSafety(unittest.TestCase):
        def setUp(self) -> None:
            self.db = MagicMock()
            # Mock firestore.transactional to just call the function
            with patch(
                "pickaladder.match.services.challenge_service.firestore",
            ) as mock_firestore:

                def side_effect(f):
                    return f

                mock_firestore.transactional.side_effect = side_effect
                self.mock_firestore = mock_firestore

        @patch("pickaladder.match.services.challenge_service.SocialCreditService")
        @patch("pickaladder.match.services.challenge_service.firestore")
        def test_wager_limit(self, mock_firestore, mock_social) -> None:
            def side_effect(f):
                return f

            mock_firestore.transactional.side_effect = side_effect

            with pytest.raises(ValueError, match="Wager cannot exceed 50 credits"):
                ChallengeService.issue_challenge(self.db, "u1", "u2", 51)

        @patch("pickaladder.match.services.challenge_service.SocialCreditService")
        @patch("pickaladder.match.services.challenge_service.firestore")
        def test_active_limit(self, mock_firestore, mock_social) -> None:
            def side_effect(f):
                return f

            mock_firestore.transactional.side_effect = side_effect

            mock_query = MagicMock()
            self.db.collection.return_value.where.return_value.where.return_value = (
                mock_query
            )
            mock_query.get.return_value = [MagicMock(), MagicMock(), MagicMock()]

            with pytest.raises(
                ValueError, match="You already have 3 active challenges"
            ):
                ChallengeService.issue_challenge(self.db, "u1", "u2", 10)

    # Note: expiration tests are harder to do with simple unittest without more patching
    # But this at least gives us some signal.
    unittest.main()
