"""Common utilities for tests."""

import unittest.mock
from collections.abc import Iterator

import pytest

from tests.mock_utils import MockFirestoreBuilder, patch_mockfirestore


@pytest.fixture(autouse=True)
def apply_global_patches() -> None:
    """Apply global monkeypatches to mockfirestore."""
    patch_mockfirestore()


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
