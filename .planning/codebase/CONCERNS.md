# Codebase Concerns

**Analysis Date:** 2025-02-23

## Tech Debt

**Monolithic Service Classes:**
- Issue: `GroupService` and `TournamentService` have grown too large, handling everything from data fetching to business logic and even some UI-adjacent enrichment.
- Files: `pickaladder/group/services/group_service.py`, `pickaladder/tournament/services/tournament_service.py`
- Impact: High cognitive load, difficulty in maintaining or extending functionality, and increased risk of side effects when making changes.
- Fix approach: Decompose these services into smaller, more focused classes or modules based on specific responsibilities (e.g., `GroupMemberService`, `GroupMatchService`).

**High Cyclomatic Complexity:**
- Issue: Several critical modules exceed complexity thresholds, leading to many linting ignores.
- Files: `pickaladder/group/utils.py`, `pickaladder/match/routes.py`, `pickaladder/user/routes.py`
- Impact: Code is difficult to read, test, and debug.
- Fix approach: Refactor complex functions into smaller, more manageable helpers. Remove `PLR0911`, `PLR0912`, and `PLR0915` from `pyproject.toml` ignore list.

**Low Type Hint Coverage:**
- Issue: A significant portion of the codebase lacks type annotations, especially in route handlers and forms.
- Files: `pickaladder/group/routes.py`, `pickaladder/auth/routes.py`, `pickaladder/match/routes.py`
- Impact: Reduced developer productivity due to lack of IDE support and increased risk of runtime `TypeError` and `AttributeError` exceptions.
- Fix approach: Progressively add type hints starting with core services and then moving to route handlers. Address the numerous `# TODO: Add type hints for Agent clarity` comments.

**Stale Configuration in `mypy.ini`:**
- Issue: `mypy.ini` contains ignore rules for libraries not currently used by the project (e.g., `sqlalchemy`).
- Files: `mypy.ini`
- Impact: Minor confusion for developers and potential masking of issues if these libraries are ever actually added.
- Fix approach: Clean up `mypy.ini` to reflect only currently used dependencies.

## Security Considerations

**Development Default for `SECRET_KEY`:**
- Issue: `SECRET_KEY` defaults to `"dev"` in development mode.
- Files: `pickaladder/config.py`
- Risk: If the application is accidentally run in production without properly setting the `SECRET_KEY` environment variable, it could lead to compromised sessions.
- Current mitigation: `SESSION_COOKIE_SECURE` is tied to `FLASK_ENV != "development"`.
- Recommendations: Ensure production deployment checklists strictly enforce the setting of `SECRET_KEY` and other sensitive environment variables.

**Low Type Safety in Auth Flows:**
- Risk: The lack of strict typing in `auth` routes and decorators could lead to subtle bugs in authentication or authorization logic.
- Files: `pickaladder/auth/routes.py`, `pickaladder/auth/decorators.py`
- Current mitigation: Basic tests and manual verification.
- Recommendations: Prioritize adding type hints and unit tests for all authentication and authorization logic.

## Fragile Areas

**Recent ACL Refactoring:**
- Files: `pickaladder/auth/`, `pickaladder/group/`, `pickaladder/tournament/`
- Why fragile: The `CHANGELOG.md` mentions a "Massive system-wide ACL reduction (Cognitive Load refactoring)". Such sweeping changes often introduce regression risks in permissions management.
- Safe modification: Carefully review existing permissions tests and add new ones for edge cases (e.g., guest users, group members vs. owners).
- Test coverage: Gaps in testing specific combinations of user roles and permissions.

**Firestore Mocking:**
- Files: `tests/`
- Why fragile: Heavy reliance on `mock-firestore` in tests may hide differences between the mock and the actual Firestore behavior (e.g., query limits, transaction behavior, or index requirements).
- Safe modification: Supplement unit tests with integration tests against a real Firestore emulator or a dedicated test project.

## Test Coverage Gaps

**Untyped Test Suites:**
- What's not tested: Most test files themselves lack type annotations, making them less robust and harder to maintain.
- Files: `tests/test_match.py`, `tests/test_user.py`, `tests/test_group.py`
- Risk: Tests might have logic errors that go unnoticed due to lack of type checking.
- Priority: Medium

**Complex E2E Flows:**
- What's not tested: Complex multi-user interactions like tournament invitations, acceptances, and bracket management.
- Files: `tests/e2e/test_e2e.py`
- Risk: Critical business flows might break after changes to shared services or routes.
- Priority: High

---

*Concerns audit: 2025-02-23*
