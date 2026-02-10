"""Common utilities for tests."""

import unittest.mock
from collections.abc import Iterator
from typing import Any

import pytest
from mockfirestore import MockFirestore

from pickaladder import create_app
from tests.mock_utils import MockFirestoreBuilder, patch_mockfirestore


@pytest.fixture
def mock_db() -> MockFirestore:
    """Fixture to provide a mock Firestore database."""
    return MockFirestore()


@pytest.fixture(autouse=True)
def apply_global_patches(mock_db: MockFirestore) -> Iterator[None]:
    """Apply global monkeypatches to mockfirestore and firebase_admin."""
    patch_mockfirestore()
    with (
        unittest.mock.patch("firebase_admin.initialize_app"),
        unittest.mock.patch("firebase_admin.firestore.client", return_value=mock_db),
        unittest.mock.patch("firebase_admin.auth"),
    ):
        yield


@pytest.fixture
def app() -> Iterator[Any]:
    """Create and configure a new app instance for each test."""
    # Global patches from apply_global_patches are already active
    app = create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SERVER_NAME": "localhost",
        }
    )
    yield app


@pytest.fixture
def mock_db_read() -> None:
    """Fixture to apply database read patches."""
    MockFirestoreBuilder.patch_db_read()


@pytest.fixture
def mock_db_write() -> None:
    """Fixture to apply database write patches."""
    MockFirestoreBuilder.patch_db_write()


@pytest.fixture
def mock_db_auth() -> Iterator[unittest.mock.MagicMock]:
    """Fixture to provide an autospec'd firebase_admin.auth mock."""
    mock_auth = MockFirestoreBuilder.patch_db_auth()
    with unittest.mock.patch("firebase_admin.auth", new=mock_auth):
        yield mock_auth
