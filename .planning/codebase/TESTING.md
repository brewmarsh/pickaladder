# Testing Patterns

**Analysis Date:** 2025-05-15

## Test Framework

**Runner:**
- [pytest](https://docs.pytest.org/) 9.0.2

**Assertion Library:**
- Built-in `assert` for pytest.
- `unittest.TestCase` assertions (e.g., `assertEqual`, `assertIn`) in legacy/structured test cases.

**Run Commands:**
```bash
pytest                  # Run all tests
pytest -w               # Watch mode (if pytest-watch is installed)
coverage run -m pytest  # Coverage
```

## Test File Organization

**Location:**
- Separate `tests/` directory at the project root.

**Naming:**
- Files prefixed with `test_`: `test_auth.py`, `test_match.py`.
- E2E tests located in `tests/e2e/`.

**Structure:**
```
tests/
├── conftest.py          # Global fixtures and patches
├── mock_utils.py        # Mocking helpers
├── test_*.py           # Unit and integration tests
└── e2e/                 # End-to-end tests (Playwright)
```

## Test Structure

**Suite Organization:**
```python
class AuthFirebaseTestCase(unittest.TestCase):
    """Test case for the auth blueprint."""

    def setUp(self) -> None:
        """Set up a test client and a comprehensive mock environment."""
        # ... patches and setup ...
        self.app = create_app({"TESTING": True})
        self.client = self.app.test_client()

    def test_feature_name(self) -> None:
        """Test description."""
        # Arrange
        # Act
        # Assert
```

**Patterns:**
- **Setup pattern**: `setUp` method in `unittest.TestCase` or `@pytest.fixture` in `conftest.py`.
- **Teardown pattern**: `tearDown` method or `addCleanup` for patches.
- **Assertion pattern**: Checking response status codes, presence of text in HTML, and verification of mock calls.

## Mocking

**Framework:**
- `unittest.mock` (MagicMock, patch)
- [mock-firestore](https://github.com/mdmintz/mock-firestore) for database mocking.

**Patterns:**
```python
@patch("pickaladder.auth.routes.send_email")
def test_successful_registration(self, mock_send_email: MagicMock) -> None:
    # ...
    self.mock_auth_service.create_user.assert_called_once()
```

**What to Mock:**
- Firebase Admin (Auth and Firestore).
- External services (Email, Imgur).
- Current application context and session.

**What NOT to Mock:**
- Data models (unless necessary for complex interactions).
- Internal utility functions (unless they have side effects).

## Fixtures and Factories

**Test Data:**
```python
MOCK_USER_ID = "user1"
MOCK_USER_PAYLOAD = {"uid": MOCK_USER_ID, "email": "user1@example.com"}
```
- Hardcoded constants for mock payloads are common in `tests/test_*.py`.

**Location:**
- Global fixtures: `tests/conftest.py`.
- Mocking utilities: `tests/mock_utils.py`.

## Coverage

**Requirements:**
- No strict requirement enforced in `pyproject.toml`, but `coverage` is listed as a dev dependency.

**View Coverage:**
```bash
coverage report
coverage html
```

## Test Types

**Unit Tests:**
- Test individual functions and model methods (e.g., `test_match.py` for `Match` class methods).

**Integration Tests:**
- Flask `test_client` is used to test routes and blueprint interactions with mocked Firebase services.

**E2E Tests:**
- [Playwright](https://playwright.dev/python/) is used for end-to-end browser testing (`tests/e2e/`).

## Common Patterns

**Async Testing:**
- Used in Playwright E2E tests (implied by `pytest-playwright`).

**Error Testing:**
```python
def test_login_invalid_password(self) -> None:
    # Mock invalid credentials
    # Assert error message in response
```

---

*Testing analysis: 2025-05-15*
