# Agent Scorecard Report

**Target Agent Profile:** Standard Agent Readiness checks (ACL & Type Safety)
**Overall Score: 94.3/100** - PASS

✅ **Status: PASSED** - This codebase is Agent-Ready.

## 🎯 Top Refactoring Targets (Agent Cognitive Load (ACL))

ACL = Complexity + (Lines of Code / 20). Target: ACL <= 10.

| Function | File | ACL | Status |
|----------|------|-----|--------|
| `format_matches_for_dashboard` | `pickaladder/user/services/match_stats.py` | 38.0 | 🔴 Red |
| `register` | `pickaladder/auth/routes.py` | 22.2 | 🔴 Red |
| `patch_db_read` | `tests/mock_utils.py` | 19.2 | 🔴 Red |
| `load_user_from_auth_source` | `pickaladder/auth/routes.py` | 16.9 | 🔴 Red |
| `edit_tournament` | `pickaladder/tournament/routes.py` | 16.6 | 🔴 Red |
| `get_recent_opponents` | `pickaladder/user/services/match_stats.py` | 16.4 | 🔴 Red |
| `edit_match` | `pickaladder/match/routes.py` | 16.0 | 🔴 Red |
| `create_app` | `pickaladder/__init__.py` | 15.1 | 🔴 Red |
| `update_tournament` | `pickaladder/tournament/services.py` | 14.9 | 🟡 Yellow |
| `view_group` | `pickaladder/group/routes.py` | 14.8 | 🟡 Yellow |

## 🛡️ Type Safety Index

Target: >90% of functions must have explicit type signatures.

| File | Type Safety Index | Status |
| :--- | :---------------: | :----- |
| tests/test_impersonation.py | 0% | ❌ |
| tests/test_rematch_logic.py | 0% | ❌ |
| tests/e2e/test_mobile_design.py | 0% | ❌ |
| tests/e2e/verify_fixes.py | 0% | ❌ |
| tests/test_config_integrity.py | 50% | ❌ |
| tests/test_user_service.py | 91% | ✅ |
| tests/test_match.py | 92% | ✅ |
| tests/test_user.py | 93% | ✅ |
| tests/e2e/conftest.py | 96% | ✅ |
| pickaladder/match/services.py | 98% | ✅ |
| app.py | 100% | ✅ |
| verify_css.py | 100% | ✅ |
| fix_imports.py | 100% | ✅ |
| scripts/migrate_teams.py | 100% | ✅ |
| scripts/sync_db.py | 100% | ✅ |
| tests/test_dupr_link.py | 100% | ✅ |
| tests/test_tournament_invites.py | 100% | ✅ |
| tests/test_user_profile_dupr.py | 100% | ✅ |
| tests/test_match_security.py | 100% | ✅ |
| tests/test_styleguide.py | 100% | ✅ |
| tests/__init__.py | 100% | ✅ |
| tests/test_pwa.py | 100% | ✅ |
| tests/test_brag_card.py | 100% | ✅ |
| tests/test_match_parser.py | 100% | ✅ |
| tests/test_tournament_utils.py | 100% | ✅ |
| tests/test_match_transaction.py | 100% | ✅ |
| tests/test_proxy_fix.py | 100% | ✅ |
| tests/test_tournament_blast.py | 100% | ✅ |
| tests/conftest.py | 100% | ✅ |
| tests/test_dashboard_tournaments.py | 100% | ✅ |
| tests/test_welcome_toast.py | 100% | ✅ |
| tests/test_utils_coverage.py | 100% | ✅ |
| tests/test_group_utils.py | 100% | ✅ |
| tests/test_team_service.py | 100% | ✅ |
| tests/test_referral.py | 100% | ✅ |
| tests/test_announcement.py | 100% | ✅ |
| tests/test_auth.py | 100% | ✅ |
| tests/test_engagement_features.py | 100% | ✅ |
| tests/test_group.py | 100% | ✅ |
| tests/test_tournament_match_integration.py | 100% | ✅ |
| tests/test_group_leaderboard.py | 100% | ✅ |
| tests/test_ghost_display.py | 100% | ✅ |
| tests/mock_utils.py | 100% | ✅ |
| tests/test_admin.py | 100% | ✅ |
| tests/test_best_buds.py | 100% | ✅ |
| tests/test_tournament.py | 100% | ✅ |
| tests/test_app.py | 100% | ✅ |
| tests/test_leaderboard_logic.py | 100% | ✅ |
| tests/test_tournament_doubles.py | 100% | ✅ |
| tests/e2e/test_e2e.py | 100% | ✅ |
| tests/e2e/verify_rivalry_ui.py | 100% | ✅ |
| tests/e2e/test_tournament.py | 100% | ✅ |
| pickaladder/errors.py | 100% | ✅ |
| pickaladder/__init__.py | 100% | ✅ |
| pickaladder/utils.py | 100% | ✅ |
| pickaladder/error_handlers.py | 100% | ✅ |
| pickaladder/extensions.py | 100% | ✅ |
| pickaladder/constants.py | 100% | ✅ |
| pickaladder/context_processors.py | 100% | ✅ |
| pickaladder/user/models.py | 100% | ✅ |
| pickaladder/user/forms.py | 100% | ✅ |
| pickaladder/user/__init__.py | 100% | ✅ |
| pickaladder/user/routes.py | 100% | ✅ |
| pickaladder/user/helpers.py | 100% | ✅ |
| pickaladder/user/services/merging.py | 100% | ✅ |
| pickaladder/user/services/__init__.py | 100% | ✅ |
| pickaladder/user/services/profile.py | 100% | ✅ |
| pickaladder/user/services/core.py | 100% | ✅ |
| pickaladder/user/services/friendship.py | 100% | ✅ |
| pickaladder/user/services/activity.py | 100% | ✅ |
| pickaladder/user/services/match_stats.py | 100% | ✅ |
| pickaladder/user/services/dashboard.py | 100% | ✅ |
| pickaladder/auth/forms.py | 100% | ✅ |
| pickaladder/auth/__init__.py | 100% | ✅ |
| pickaladder/auth/routes.py | 100% | ✅ |
| pickaladder/auth/decorators.py | 100% | ✅ |
| pickaladder/tournament/services.py | 100% | ✅ |
| pickaladder/tournament/models.py | 100% | ✅ |
| pickaladder/tournament/forms.py | 100% | ✅ |
| pickaladder/tournament/__init__.py | 100% | ✅ |
| pickaladder/tournament/utils.py | 100% | ✅ |
| pickaladder/tournament/routes.py | 100% | ✅ |
| pickaladder/teams/services.py | 100% | ✅ |
| pickaladder/teams/models.py | 100% | ✅ |
| pickaladder/teams/forms.py | 100% | ✅ |
| pickaladder/teams/__init__.py | 100% | ✅ |
| pickaladder/teams/routes.py | 100% | ✅ |
| pickaladder/match/models.py | 100% | ✅ |
| pickaladder/match/forms.py | 100% | ✅ |
| pickaladder/match/__init__.py | 100% | ✅ |
| pickaladder/match/routes.py | 100% | ✅ |
| pickaladder/admin/services.py | 100% | ✅ |
| pickaladder/admin/__init__.py | 100% | ✅ |
| pickaladder/admin/routes.py | 100% | ✅ |
| pickaladder/group/models.py | 100% | ✅ |
| pickaladder/group/forms.py | 100% | ✅ |
| pickaladder/group/__init__.py | 100% | ✅ |
| pickaladder/group/utils.py | 100% | ✅ |
| pickaladder/group/routes.py | 100% | ✅ |
| pickaladder/group/services/__init__.py | 100% | ✅ |
| pickaladder/group/services/leaderboard.py | 100% | ✅ |
| pickaladder/group/services/stats.py | 100% | ✅ |
| pickaladder/group/services/group_service.py | 100% | ✅ |
| pickaladder/group/services/match_parser.py | 100% | ✅ |
| pickaladder/core/__init__.py | 100% | ✅ |
| pickaladder/core/types.py | 100% | ✅ |
| pickaladder/core/constants.py | 100% | ✅ |
| pickaladder/main/__init__.py | 100% | ✅ |
| pickaladder/main/routes.py | 100% | ✅ |

## 🤖 Agent Prompts for Remediation (CRAFT Format)

### File: `tests/test_impersonation.py` - Low Type Safety
> **Context**: You are a Python Developer focused on static analysis.
> **Request**: Add PEP 484 type hints to `tests/test_impersonation.py`.
> **Actions**:
> - Analyze functions missing explicit type signatures.
> - Add comprehensive type hints to arguments and return values.
> - Use the `typing` module for complex structures.
> **Frame**: Target 90% type coverage. Do not change runtime logic.
> **Template**: The full updated content of the Python file.

### File: `tests/test_rematch_logic.py` - Low Type Safety
> **Context**: You are a Python Developer focused on static analysis.
> **Request**: Add PEP 484 type hints to `tests/test_rematch_logic.py`.
> **Actions**:
> - Analyze functions missing explicit type signatures.
> - Add comprehensive type hints to arguments and return values.
> - Use the `typing` module for complex structures.
> **Frame**: Target 90% type coverage. Do not change runtime logic.
> **Template**: The full updated content of the Python file.

### File: `tests/test_config_integrity.py` - Low Type Safety
> **Context**: You are a Python Developer focused on static analysis.
> **Request**: Add PEP 484 type hints to `tests/test_config_integrity.py`.
> **Actions**:
> - Analyze functions missing explicit type signatures.
> - Add comprehensive type hints to arguments and return values.
> - Use the `typing` module for complex structures.
> **Frame**: Target 90% type coverage. Do not change runtime logic.
> **Template**: The full updated content of the Python file.

### File: `tests/mock_utils.py` - High Cognitive Load
> **Context**: You are a Senior Python Engineer focused on code maintainability.
> **Request**: Refactor functions in `tests/mock_utils.py` with Red ACL scores.
> **Actions**:
> - Target functions: `patch_db_read`.
> - Extract nested logic into smaller helper functions.
> - Ensure all units result in an ACL score < 10.
> **Frame**: Keep functions under 50 lines. Ensure all tests pass.
> **Template**: Markdown code blocks for the refactored code.

### File: `tests/e2e/test_mobile_design.py` - Low Type Safety
> **Context**: You are a Python Developer focused on static analysis.
> **Request**: Add PEP 484 type hints to `tests/e2e/test_mobile_design.py`.
> **Actions**:
> - Analyze functions missing explicit type signatures.
> - Add comprehensive type hints to arguments and return values.
> - Use the `typing` module for complex structures.
> **Frame**: Target 90% type coverage. Do not change runtime logic.
> **Template**: The full updated content of the Python file.

### File: `tests/e2e/verify_fixes.py` - Low Type Safety
> **Context**: You are a Python Developer focused on static analysis.
> **Request**: Add PEP 484 type hints to `tests/e2e/verify_fixes.py`.
> **Actions**:
> - Analyze functions missing explicit type signatures.
> - Add comprehensive type hints to arguments and return values.
> - Use the `typing` module for complex structures.
> **Frame**: Target 90% type coverage. Do not change runtime logic.
> **Template**: The full updated content of the Python file.

### File: `pickaladder/__init__.py` - High Cognitive Load
> **Context**: You are a Senior Python Engineer focused on code maintainability.
> **Request**: Refactor functions in `pickaladder/__init__.py` with Red ACL scores.
> **Actions**:
> - Target functions: `create_app`.
> - Extract nested logic into smaller helper functions.
> - Ensure all units result in an ACL score < 10.
> **Frame**: Keep functions under 50 lines. Ensure all tests pass.
> **Template**: Markdown code blocks for the refactored code.

### File: `pickaladder/user/services/match_stats.py` - High Cognitive Load
> **Context**: You are a Senior Python Engineer focused on code maintainability.
> **Request**: Refactor functions in `pickaladder/user/services/match_stats.py` with Red ACL scores.
> **Actions**:
> - Target functions: `format_matches_for_dashboard`, `get_recent_opponents`.
> - Extract nested logic into smaller helper functions.
> - Ensure all units result in an ACL score < 10.
> **Frame**: Keep functions under 50 lines. Ensure all tests pass.
> **Template**: Markdown code blocks for the refactored code.

### File: `pickaladder/auth/routes.py` - High Cognitive Load
> **Context**: You are a Senior Python Engineer focused on code maintainability.
> **Request**: Refactor functions in `pickaladder/auth/routes.py` with Red ACL scores.
> **Actions**:
> - Target functions: `load_user_from_auth_source`, `register`.
> - Extract nested logic into smaller helper functions.
> - Ensure all units result in an ACL score < 10.
> **Frame**: Keep functions under 50 lines. Ensure all tests pass.
> **Template**: Markdown code blocks for the refactored code.

### File: `pickaladder/tournament/routes.py` - High Cognitive Load
> **Context**: You are a Senior Python Engineer focused on code maintainability.
> **Request**: Refactor functions in `pickaladder/tournament/routes.py` with Red ACL scores.
> **Actions**:
> - Target functions: `edit_tournament`.
> - Extract nested logic into smaller helper functions.
> - Ensure all units result in an ACL score < 10.
> **Frame**: Keep functions under 50 lines. Ensure all tests pass.
> **Template**: Markdown code blocks for the refactored code.

### File: `pickaladder/match/routes.py` - High Cognitive Load
> **Context**: You are a Senior Python Engineer focused on code maintainability.
> **Request**: Refactor functions in `pickaladder/match/routes.py` with Red ACL scores.
> **Actions**:
> - Target functions: `edit_match`.
> - Extract nested logic into smaller helper functions.
> - Ensure all units result in an ACL score < 10.
> **Frame**: Keep functions under 50 lines. Ensure all tests pass.
> **Template**: Markdown code blocks for the refactored code.


### 📂 Full File Analysis

| File | Score | Issues |
| :--- | :---: | :--- |
| app.py | 100 ✅ |  |
| verify_css.py | 100 ✅ |  |
| fix_imports.py | 100 ✅ |  |
| scripts/migrate_teams.py | 90 ✅ | 2 Yellow ACL functions (-10) |
| scripts/sync_db.py | 100 ✅ |  |
| tests/test_dupr_link.py | 100 ✅ |  |
| tests/test_match.py | 88 ✅ | Bloated File: 274 lines (-7), 1 Yellow ACL functions (-5) |
| tests/test_tournament_invites.py | 100 ✅ |  |
| tests/test_user_profile_dupr.py | 100 ✅ |  |
| tests/test_match_security.py | 100 ✅ |  |
| tests/test_styleguide.py | 100 ✅ |  |
| tests/test_impersonation.py | 80 ✅ | Type Safety Index 0% < 90% (-20) |
| tests/__init__.py | 100 ✅ |  |
| tests/test_pwa.py | 100 ✅ |  |
| tests/test_rematch_logic.py | 80 ✅ | Type Safety Index 0% < 90% (-20) |
| tests/test_brag_card.py | 100 ✅ |  |
| tests/test_match_parser.py | 100 ✅ |  |
| tests/test_user_service.py | 100 ✅ |  |
| tests/test_user.py | 90 ✅ | Bloated File: 309 lines (-10) |
| tests/test_tournament_utils.py | 100 ✅ |  |
| tests/test_match_transaction.py | 100 ✅ |  |
| tests/test_config_integrity.py | 80 ✅ | Type Safety Index 50% < 90% (-20) |
| tests/test_proxy_fix.py | 100 ✅ |  |
| tests/test_tournament_blast.py | 95 ✅ | 1 Yellow ACL functions (-5) |
| tests/conftest.py | 100 ✅ |  |
| tests/test_dashboard_tournaments.py | 100 ✅ |  |
| tests/test_welcome_toast.py | 100 ✅ |  |
| tests/test_utils_coverage.py | 78 ✅ | Bloated File: 428 lines (-22) |
| tests/test_group_utils.py | 100 ✅ |  |
| tests/test_team_service.py | 100 ✅ |  |
| tests/test_referral.py | 100 ✅ |  |
| tests/test_announcement.py | 100 ✅ |  |
| tests/test_auth.py | 97 ✅ | Bloated File: 238 lines (-3) |
| tests/test_engagement_features.py | 100 ✅ |  |
| tests/test_group.py | 89 ✅ | Bloated File: 317 lines (-11) |
| tests/test_tournament_match_integration.py | 100 ✅ |  |
| tests/test_group_leaderboard.py | 95 ✅ | 1 Yellow ACL functions (-5) |
| tests/test_ghost_display.py | 100 ✅ |  |
| tests/mock_utils.py | 80 ✅ | 1 Red ACL functions (-15), 1 Yellow ACL functions (-5) |
| tests/test_admin.py | 100 ✅ |  |
| tests/test_best_buds.py | 95 ✅ | 1 Yellow ACL functions (-5) |
| tests/test_tournament.py | 71 ✅ | Bloated File: 499 lines (-29) |
| tests/test_app.py | 100 ✅ |  |
| tests/test_leaderboard_logic.py | 100 ✅ |  |
| tests/test_tournament_doubles.py | 100 ✅ |  |
| tests/e2e/conftest.py | 71 ✅ | Bloated File: 394 lines (-19), 2 Yellow ACL functions (-10) |
| tests/e2e/test_e2e.py | 95 ✅ | 1 Yellow ACL functions (-5) |
| tests/e2e/verify_rivalry_ui.py | 100 ✅ |  |
| tests/e2e/test_mobile_design.py | 80 ✅ | Type Safety Index 0% < 90% (-20) |
| tests/e2e/test_tournament.py | 100 ✅ |  |
| tests/e2e/verify_fixes.py | 80 ✅ | Type Safety Index 0% < 90% (-20) |
| pickaladder/errors.py | 100 ✅ |  |
| pickaladder/__init__.py | 81 ✅ | Bloated File: 246 lines (-4), 1 Red ACL functions (-15) |
| pickaladder/utils.py | 100 ✅ |  |
| pickaladder/error_handlers.py | 100 ✅ |  |
| pickaladder/extensions.py | 100 ✅ |  |
| pickaladder/constants.py | 100 ✅ |  |
| pickaladder/context_processors.py | 95 ✅ | 1 Yellow ACL functions (-5) |
| pickaladder/user/models.py | 100 ✅ |  |
| pickaladder/user/forms.py | 100 ✅ |  |
| pickaladder/user/__init__.py | 100 ✅ |  |
| pickaladder/user/routes.py | 97 ✅ | Bloated File: 233 lines (-3) |
| pickaladder/user/helpers.py | 100 ✅ |  |
| pickaladder/user/services/merging.py | 90 ✅ | 2 Yellow ACL functions (-10) |
| pickaladder/user/services/__init__.py | 99 ✅ | Bloated File: 212 lines (-1) |
| pickaladder/user/services/profile.py | 100 ✅ |  |
| pickaladder/user/services/core.py | 89 ✅ | Bloated File: 264 lines (-6), 1 Yellow ACL functions (-5) |
| pickaladder/user/services/friendship.py | 100 ✅ |  |
| pickaladder/user/services/activity.py | 70 ✅ | Bloated File: 303 lines (-10), 4 Yellow ACL functions (-20) |
| pickaladder/user/services/match_stats.py | 51 ❌ | Bloated File: 394 lines (-19), 2 Red ACL functions (-30) |
| pickaladder/user/services/dashboard.py | 100 ✅ |  |
| pickaladder/auth/forms.py | 100 ✅ |  |
| pickaladder/auth/__init__.py | 100 ✅ |  |
| pickaladder/auth/routes.py | 53 ❌ | Bloated File: 329 lines (-12), 2 Red ACL functions (-30), 1 Yellow ACL functions (-5) |
| pickaladder/auth/decorators.py | 100 ✅ |  |
| pickaladder/tournament/services.py | 39 ❌ | Bloated File: 712 lines (-51), 2 Yellow ACL functions (-10) |
| pickaladder/tournament/models.py | 100 ✅ |  |
| pickaladder/tournament/forms.py | 100 ✅ |  |
| pickaladder/tournament/__init__.py | 100 ✅ |  |
| pickaladder/tournament/utils.py | 95 ✅ | 1 Yellow ACL functions (-5) |
| pickaladder/tournament/routes.py | 63 ❌ | Bloated File: 375 lines (-17), 1 Red ACL functions (-15), 1 Yellow ACL functions (-5) |
| pickaladder/teams/services.py | 92 ✅ | Bloated File: 230 lines (-3), 1 Yellow ACL functions (-5) |
| pickaladder/teams/models.py | 100 ✅ |  |
| pickaladder/teams/forms.py | 100 ✅ |  |
| pickaladder/teams/__init__.py | 100 ✅ |  |
| pickaladder/teams/routes.py | 100 ✅ |  |
| pickaladder/match/services.py | 40 ❌ | Bloated File: 802 lines (-60) |
| pickaladder/match/models.py | 100 ✅ |  |
| pickaladder/match/forms.py | 100 ✅ |  |
| pickaladder/match/__init__.py | 100 ✅ |  |
| pickaladder/match/routes.py | 75 ✅ | 1 Red ACL functions (-15), 2 Yellow ACL functions (-10) |
| pickaladder/admin/services.py | 100 ✅ |  |
| pickaladder/admin/__init__.py | 100 ✅ |  |
| pickaladder/admin/routes.py | 83 ✅ | Bloated File: 322 lines (-12), 1 Yellow ACL functions (-5) |
| pickaladder/group/models.py | 100 ✅ |  |
| pickaladder/group/forms.py | 100 ✅ |  |
| pickaladder/group/__init__.py | 100 ✅ |  |
| pickaladder/group/utils.py | 58 ❌ | Bloated File: 523 lines (-32), 2 Yellow ACL functions (-10) |
| pickaladder/group/routes.py | 78 ✅ | Bloated File: 373 lines (-17), 1 Yellow ACL functions (-5) |
| pickaladder/group/services/__init__.py | 100 ✅ |  |
| pickaladder/group/services/leaderboard.py | 91 ✅ | Bloated File: 290 lines (-9) |
| pickaladder/group/services/stats.py | 95 ✅ | 1 Yellow ACL functions (-5) |
| pickaladder/group/services/group_service.py | 57 ❌ | Bloated File: 586 lines (-38), 1 Yellow ACL functions (-5) |
| pickaladder/group/services/match_parser.py | 95 ✅ | 1 Yellow ACL functions (-5) |
| pickaladder/core/__init__.py | 100 ✅ |  |
| pickaladder/core/types.py | 100 ✅ |  |
| pickaladder/core/constants.py | 100 ✅ |  |
| pickaladder/main/__init__.py | 100 ✅ |  |
| pickaladder/main/routes.py | 100 ✅ |  |

---
*Generated by Agent-Scorecard*