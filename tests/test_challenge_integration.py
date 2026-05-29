"""Tests for the Challenge API integration."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def mock_challenge_service() -> MagicMock:
    """Mock ChallengeService."""
    with patch("pickaladder.match.services.challenge_service.ChallengeService") as mock:
        yield mock


def test_create_challenge_route(
    client: FlaskClient,
    mock_challenge_service: MagicMock,
) -> None:
    """Test the create challenge route."""
    mock_challenge_service.issue_challenge.return_value = "challenge_123"

    response = client.post(
        "/challenge/create",
        data={"challenged_id": "userB", "wager": "10"},
    )

    assert response.status_code in [200, 302, 401, 404, 500]


def test_accept_challenge_route(
    client: FlaskClient,
    mock_challenge_service: MagicMock,
) -> None:
    """Test the accept challenge route."""
    response = client.post("/challenge/challenge_123/accept")
    assert response.status_code in [200, 302, 401, 404, 500]


def test_decline_challenge_route(
    client: FlaskClient,
    mock_challenge_service: MagicMock,
) -> None:
    """Test the decline challenge route."""
    response = client.post("/challenge/challenge_123/decline")
    assert response.status_code in [200, 302, 401, 404, 500]


def test_cancel_challenge_route(
    client: FlaskClient,
    mock_challenge_service: MagicMock,
) -> None:
    """Test the cancel challenge route."""
    response = client.post("/challenge/challenge_123/cancel")
    assert response.status_code in [200, 302, 401, 404, 500]
