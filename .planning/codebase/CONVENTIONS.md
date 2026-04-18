# Coding Conventions

**Analysis Date:** 2025-05-15

## Naming Patterns

**Files:**
- Snake case for Python files: `routes.py`, `models.py`, `utils.py`.
- HTML templates use snake case: `record_match.html`.

**Functions:**
- Snake case: `_verify_bearer_token()`, `get_matchup_info()`.
- Private helper functions are prefixed with an underscore: `_handle_impersonation()`.

**Variables:**
- Snake case: `auth_header`, `id_token`.
- Constants are UPPER_CASE: `MOCK_USER_ID`.

**Types:**
- Classes use PascalCase: `Match`, `MatchSubmission`.
- TypedDicts use PascalCase: `MatchDict`, `Score`.

## Code Style

**Formatting:**
- [Ruff](https://beta.ruff.rs/docs/) is used for formatting.
- Line length is set to 88 (Black style).
- Uses double quotes for strings.
- Indent with 4 spaces.

**Linting:**
- [Ruff](https://beta.ruff.rs/docs/) is used for linting.
- Enabled rules: Pyflakes (`F`), pycodestyle (`E`, `W`), isort (`I`), pyupgrade (`UP`), and Pylint (`PL`).
- Specific ignores: `E501` (line-too-long, handled by formatter), complexity ignores (`PLR0911`, `PLR0912`, `PLR0915`).
- Maximum complexity is set to 10.

## Import Organization

**Order:**
Managed by Ruff (`isort` rules):
1. Future imports (`from __future__ import annotations`).
2. Standard library imports.
3. Third-party library imports.
4. Local application imports.

**Path Aliases:**
- No path aliases detected; relative imports (e.g., `from . import bp`) and absolute imports (e.g., `from pickaladder.user import UserService`) are used.

## Error Handling

**Patterns:**
- Uses custom exception classes defined in `pickaladder/errors.py`.
- `try-except` blocks are used for external service calls (Firebase, email).
- Flask error handlers are used to catch and respond to specific errors (see `pickaladder/error_handlers.py`).

## Logging

**Framework:** Flask's built-in `current_app.logger`.

**Patterns:**
- `current_app.logger.debug()` for development-level tracing.
- Logging is used for token verification failures and other background processes.

## Comments

**When to Comment:**
- Complex logic in models (e.g., matchup info calculation in `pickaladder/match/models.py`).
- TODOs for future refactoring or missing features.

**JSDoc/TSDoc:**
- Not applicable (Python project), but PEP 257 docstrings are enforced by Ruff.

## Function Design

**Size:**
- Aim for small, focused functions.
- Complex logic in routes is often extracted into private helper functions (`_populate_g_user`, etc.).

**Parameters:**
- Type hints are required for parameters.
- Default values are used where appropriate.

**Return Values:**
- Type hints are required for return values.
- Uses `| None` for optional returns and `tuple` for multiple returns.

## Module Design

**Exports:**
- Blueprints are defined in `__init__.py` of each module and imported in `pickaladder/__init__.py`.

**Barrel Files:**
- `__init__.py` files are used to define blueprints and sometimes to expose key classes/functions.

---

*Convention analysis: 2025-05-15*
