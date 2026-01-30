# Codebase Audit Report

This report details the files that violate the line count and cyclomatic complexity rules.

## Line Count Violations (limit: 300 lines)

**Note:** Ruff does not currently support a rule for enforcing a maximum number of lines per file. The following list was generated manually.

* `pickaladder/user/routes.py`: 965 lines
* `pickaladder/group/routes.py`: 812 lines
* `pickaladder/group/utils.py`: 564 lines
* `pickaladder/match/routes.py`: 539 lines
* `pickaladder/auth/routes.py`: 323 lines

## Ruff Violations

| File | Violation Count | Violations |
|---|---|---|
| app.py | 1 | ANN201 |
| pickaladder/__init__.py | 10 | ANN001, ANN201, ANN202, C901 |
| pickaladder/admin/routes.py | 14 | ANN001, ANN201 |
| pickaladder/auth/decorators.py | 8 | ANN001, ANN002, ANN003, ANN201, ANN202 |
| pickaladder/auth/forms.py | 4 | ANN001, ANN201 |
| pickaladder/auth/routes.py | 9 | ANN001, ANN201, ANN202 |
| pickaladder/error_handlers.py | 14 | ANN001, ANN201 |
| pickaladder/errors.py | 9 | ANN001, ANN204 |
| pickaladder/group/routes.py | 28 | ANN001, ANN201, ANN202, C901 |
| pickaladder/group/utils.py | 29 | ANN001, ANN201, ANN202, C901 |
| pickaladder/match/forms.py | 6 | ANN001, ANN201 |
| pickaladder/match/routes.py | 23 | ANN001, ANN201, ANN202, C901 |
| pickaladder/user/routes.py | 24 | ANN001, ANN201, ANN202, ANN204, C901 |
| pickaladder/user/utils.py | 4 | ANN001, ANN201 |
| pickaladder/utils.py | 5 | ANN001, ANN003, ANN201 |
| tests/e2e/conftest.py | 82 | ANN001, ANN003, ANN201, ANN202, ANN204, C901 |
| tests/e2e/test_e2e.py | 4 | ANN001, ANN201 |
| tests/test_admin.py | 10 | ANN001, ANN201, ANN202 |
| tests/test_app.py | 7 | ANN001, ANN201 |
| tests/test_auth.py | 11 | ANN001, ANN201, ANN202 |
| tests/test_group.py | 8 | ANN201, ANN202 |
| tests/test_group_leaderboard.py | 10 | ANN001, ANN201, ANN202 |
| tests/test_group_utils.py | 2 | ANN001, ANN201 |
| tests/test_match.py | 12 | ANN001, ANN201, ANN202 |
| tests/test_proxy_fix.py | 3 | ANN201, ANN202 |
| tests/test_user.py | 18 | ANN001, ANN201, ANN202 |
| tests/test_user_profile_dupr.py | 3 | ANN201 |
