import pytest
from unittest.mock import MagicMock
from pickaladder.teams.repository import TeamRepository

@pytest.fixture
def mock_db():
    return MagicMock()

def test_repository_initialization():
    assert TeamRepository.COLLECTION_NAME == "teams"

# More tests will be added in Task 1
