# Agent Scorecard Report

**Target Agent Profile:** Standard Agent Readiness checks (ACL & Type Safety)
**Overall Score: 92.2/100** - PASS

✅ **Status: PASSED** - This codebase is Agent-Ready.

## 🎯 Top Refactoring Targets (Agent Cognitive Load (ACL))

ACL = Complexity + (Lines of Code / 20). Target: ACL <= 10.

| Function | File | ACL | Status |
|----------|------|-----|--------|
| `record_match` | `pickaladder/match/routes.py` | 34.8 | 🔴 Red |
| `get_group_leaderboard` | `pickaladder/group/utils.py` | 32.5 | 🔴 Red |
| `create_app` | `pickaladder/__init__.py` | 28.9 | 🔴 Red |
| `_calculate_leaderboard_from_matches` | `pickaladder/group/utils.py` | 26.4 | 🔴 Red |
| `get_leaderboard_trend_data` | `pickaladder/group/utils.py` | 26.2 | 🔴 Red |
| `_fetch_group_teams` | `pickaladder/group/routes.py` | 24.9 | 🔴 Red |
| `patch_mockfirestore` | `tests/conftest.py` | 23.2 | 🔴 Red |
| `_migrate_ghost_references` | `pickaladder/user/services.py` | 23.2 | 🔴 Red |
| `view_team` | `pickaladder/teams/routes.py` | 21.8 | 🔴 Red |
| `_initialize_firebase` | `pickaladder/__init__.py` | 19.7 | 🟡 Yellow |

## 🛡️ Type Safety Index

Target: >90% of functions must have explicit type signatures.

| File | Type Safety Index | Status |
| :--- | :---------------: | :----- |
| app.py | 0% | ❌ |
| scripts/migrate_teams.py | 0% | ❌ |
| tests/conftest.py | 0% | ❌ |
| tests/test_dashboard_tournaments.py | 0% | ❌ |
| pickaladder/errors.py | 0% | ❌ |
| pickaladder/__init__.py | 0% | ❌ |
| pickaladder/error_handlers.py | 0% | ❌ |
| pickaladder/auth/forms.py | 0% | ❌ |
| pickaladder/auth/routes.py | 0% | ❌ |
| pickaladder/auth/decorators.py | 0% | ❌ |
| pickaladder/teams/models.py | 0% | ❌ |
| pickaladder/teams/utils.py | 0% | ❌ |
| pickaladder/match/forms.py | 0% | ❌ |
| pickaladder/admin/routes.py | 0% | ❌ |
| tests/test_tournament_blast.py | 71% | ❌ |
| tests/test_utils_coverage.py | 88% | ❌ |
| tests/test_user_service.py | 90% | ✅ |
| tests/test_tournament.py | 93% | ✅ |
| tests/test_match.py | 100% | ✅ |
| tests/test_tournament_invites.py | 100% | ✅ |
| tests/test_user_profile_dupr.py | 100% | ✅ |
| tests/__init__.py | 100% | ✅ |
| tests/test_user.py | 100% | ✅ |
| tests/test_tournament_utils.py | 100% | ✅ |
| tests/test_proxy_fix.py | 100% | ✅ |
| tests/test_welcome_toast.py | 100% | ✅ |
| tests/test_group_utils.py | 100% | ✅ |
| tests/test_auth.py | 100% | ✅ |
| tests/test_group.py | 100% | ✅ |
| tests/test_tournament_match_integration.py | 100% | ✅ |
| tests/test_group_leaderboard.py | 100% | ✅ |
| tests/test_ghost_display.py | 100% | ✅ |
| tests/test_admin.py | 100% | ✅ |
| tests/test_best_buds.py | 100% | ✅ |
| tests/test_app.py | 100% | ✅ |
| tests/e2e/conftest.py | 100% | ✅ |
| tests/e2e/test_e2e.py | 100% | ✅ |
| tests/e2e/verify_rivalry_ui.py | 100% | ✅ |
| tests/e2e/test_tournament.py | 100% | ✅ |
| pickaladder/utils.py | 100% | ✅ |
| pickaladder/extensions.py | 100% | ✅ |
| pickaladder/constants.py | 100% | ✅ |
| pickaladder/user/services.py | 100% | ✅ |
| pickaladder/user/models.py | 100% | ✅ |
| pickaladder/user/forms.py | 100% | ✅ |
| pickaladder/user/__init__.py | 100% | ✅ |
| pickaladder/user/routes.py | 100% | ✅ |
| pickaladder/user/helpers.py | 100% | ✅ |
| pickaladder/auth/__init__.py | 100% | ✅ |
| pickaladder/tournament/services.py | 100% | ✅ |
| pickaladder/tournament/forms.py | 100% | ✅ |
| pickaladder/tournament/__init__.py | 100% | ✅ |
| pickaladder/tournament/utils.py | 100% | ✅ |
| pickaladder/tournament/routes.py | 100% | ✅ |
| pickaladder/teams/forms.py | 100% | ✅ |
| pickaladder/teams/__init__.py | 100% | ✅ |
| pickaladder/teams/routes.py | 100% | ✅ |
| pickaladder/match/__init__.py | 100% | ✅ |
| pickaladder/match/routes.py | 100% | ✅ |
| pickaladder/admin/__init__.py | 100% | ✅ |
| pickaladder/group/forms.py | 100% | ✅ |
| pickaladder/group/__init__.py | 100% | ✅ |
| pickaladder/group/utils.py | 100% | ✅ |
| pickaladder/group/routes.py | 100% | ✅ |

## 🤖 Agent Prompts for Remediation

### File: `app.py`
- **Type Safety**: Coverage is 0%. Prompt: 'Add explicit type signatures to all functions in `app.py` to meet the 90% Type Safety Index requirement.'

### File: `scripts/migrate_teams.py`
- **Type Safety**: Coverage is 0%. Prompt: 'Add explicit type signatures to all functions in `scripts/migrate_teams.py` to meet the 90% Type Safety Index requirement.'

### File: `tests/test_tournament_blast.py`
- **Type Safety**: Coverage is 71%. Prompt: 'Add explicit type signatures to all functions in `tests/test_tournament_blast.py` to meet the 90% Type Safety Index requirement.'

### File: `tests/conftest.py`
- **Critical ACL**: Functions `patch_mockfirestore` have Red ACL (>20). Prompt: 'Refactor functions in `tests/conftest.py` with high cognitive load to bring ACL below 10. Split complex logic and reduce function length.'
- **Type Safety**: Coverage is 0%. Prompt: 'Add explicit type signatures to all functions in `tests/conftest.py` to meet the 90% Type Safety Index requirement.'

### File: `tests/test_dashboard_tournaments.py`
- **Type Safety**: Coverage is 0%. Prompt: 'Add explicit type signatures to all functions in `tests/test_dashboard_tournaments.py` to meet the 90% Type Safety Index requirement.'

### File: `tests/test_utils_coverage.py`
- **Type Safety**: Coverage is 88%. Prompt: 'Add explicit type signatures to all functions in `tests/test_utils_coverage.py` to meet the 90% Type Safety Index requirement.'

### File: `pickaladder/errors.py`
- **Type Safety**: Coverage is 0%. Prompt: 'Add explicit type signatures to all functions in `pickaladder/errors.py` to meet the 90% Type Safety Index requirement.'

### File: `pickaladder/__init__.py`
- **Critical ACL**: Functions `create_app` have Red ACL (>20). Prompt: 'Refactor functions in `pickaladder/__init__.py` with high cognitive load to bring ACL below 10. Split complex logic and reduce function length.'
- **Type Safety**: Coverage is 0%. Prompt: 'Add explicit type signatures to all functions in `pickaladder/__init__.py` to meet the 90% Type Safety Index requirement.'

### File: `pickaladder/error_handlers.py`
- **Type Safety**: Coverage is 0%. Prompt: 'Add explicit type signatures to all functions in `pickaladder/error_handlers.py` to meet the 90% Type Safety Index requirement.'

### File: `pickaladder/user/services.py`
- **Critical ACL**: Functions `_migrate_ghost_references` have Red ACL (>20). Prompt: 'Refactor functions in `pickaladder/user/services.py` with high cognitive load to bring ACL below 10. Split complex logic and reduce function length.'

### File: `pickaladder/auth/forms.py`
- **Type Safety**: Coverage is 0%. Prompt: 'Add explicit type signatures to all functions in `pickaladder/auth/forms.py` to meet the 90% Type Safety Index requirement.'

### File: `pickaladder/auth/routes.py`
- **Type Safety**: Coverage is 0%. Prompt: 'Add explicit type signatures to all functions in `pickaladder/auth/routes.py` to meet the 90% Type Safety Index requirement.'

### File: `pickaladder/auth/decorators.py`
- **Type Safety**: Coverage is 0%. Prompt: 'Add explicit type signatures to all functions in `pickaladder/auth/decorators.py` to meet the 90% Type Safety Index requirement.'

### File: `pickaladder/teams/models.py`
- **Type Safety**: Coverage is 0%. Prompt: 'Add explicit type signatures to all functions in `pickaladder/teams/models.py` to meet the 90% Type Safety Index requirement.'

### File: `pickaladder/teams/utils.py`
- **Type Safety**: Coverage is 0%. Prompt: 'Add explicit type signatures to all functions in `pickaladder/teams/utils.py` to meet the 90% Type Safety Index requirement.'

### File: `pickaladder/teams/routes.py`
- **Critical ACL**: Functions `view_team` have Red ACL (>20). Prompt: 'Refactor functions in `pickaladder/teams/routes.py` with high cognitive load to bring ACL below 10. Split complex logic and reduce function length.'

### File: `pickaladder/match/forms.py`
- **Type Safety**: Coverage is 0%. Prompt: 'Add explicit type signatures to all functions in `pickaladder/match/forms.py` to meet the 90% Type Safety Index requirement.'

### File: `pickaladder/match/routes.py`
- **Critical ACL**: Functions `record_match` have Red ACL (>20). Prompt: 'Refactor functions in `pickaladder/match/routes.py` with high cognitive load to bring ACL below 10. Split complex logic and reduce function length.'

### File: `pickaladder/admin/routes.py`
- **Type Safety**: Coverage is 0%. Prompt: 'Add explicit type signatures to all functions in `pickaladder/admin/routes.py` to meet the 90% Type Safety Index requirement.'

### File: `pickaladder/group/utils.py`
- **Critical ACL**: Functions `_calculate_leaderboard_from_matches`, `get_group_leaderboard`, `get_leaderboard_trend_data` have Red ACL (>20). Prompt: 'Refactor functions in `pickaladder/group/utils.py` with high cognitive load to bring ACL below 10. Split complex logic and reduce function length.'

### File: `pickaladder/group/routes.py`
- **Critical ACL**: Functions `_fetch_group_teams` have Red ACL (>20). Prompt: 'Refactor functions in `pickaladder/group/routes.py` with high cognitive load to bring ACL below 10. Split complex logic and reduce function length.'


### 📂 Full File Analysis

| File | Score | Issues |
| :--- | :---: | :--- |
| app.py | 80 ✅ | Type Safety Index 0% < 90% (-20) |
| scripts/migrate_teams.py | 70 ✅ | 2 Yellow ACL functions (-10), Type Safety Index 0% < 90% (-20) |
| tests/test_match.py | 95 ✅ | 1 Yellow ACL functions (-5) |
| tests/test_tournament_invites.py | 100 ✅ |  |
| tests/test_user_profile_dupr.py | 100 ✅ |  |
| tests/__init__.py | 100 ✅ |  |
| tests/test_user_service.py | 100 ✅ |  |
| tests/test_user.py | 100 ✅ |  |
| tests/test_tournament_utils.py | 100 ✅ |  |
| tests/test_proxy_fix.py | 100 ✅ |  |
| tests/test_tournament_blast.py | 75 ✅ | 1 Yellow ACL functions (-5), Type Safety Index 71% < 90% (-20) |
| tests/conftest.py | 65 ❌ | 1 Red ACL functions (-15), Type Safety Index 0% < 90% (-20) |
| tests/test_dashboard_tournaments.py | 80 ✅ | Type Safety Index 0% < 90% (-20) |
| tests/test_welcome_toast.py | 100 ✅ |  |
| tests/test_utils_coverage.py | 80 ✅ | Type Safety Index 88% < 90% (-20) |
| tests/test_group_utils.py | 100 ✅ |  |
| tests/test_auth.py | 100 ✅ |  |
| tests/test_group.py | 100 ✅ |  |
| tests/test_tournament_match_integration.py | 100 ✅ |  |
| tests/test_group_leaderboard.py | 95 ✅ | 1 Yellow ACL functions (-5) |
| tests/test_ghost_display.py | 100 ✅ |  |
| tests/test_admin.py | 100 ✅ |  |
| tests/test_best_buds.py | 95 ✅ | 1 Yellow ACL functions (-5) |
| tests/test_tournament.py | 100 ✅ |  |
| tests/test_app.py | 100 ✅ |  |
| tests/e2e/conftest.py | 90 ✅ | 2 Yellow ACL functions (-10) |
| tests/e2e/test_e2e.py | 95 ✅ | 1 Yellow ACL functions (-5) |
| tests/e2e/verify_rivalry_ui.py | 100 ✅ |  |
| tests/e2e/test_tournament.py | 100 ✅ |  |
| pickaladder/errors.py | 80 ✅ | Type Safety Index 0% < 90% (-20) |
| pickaladder/__init__.py | 60 ❌ | 1 Red ACL functions (-15), 1 Yellow ACL functions (-5), Type Safety Index 0% < 90% (-20) |
| pickaladder/utils.py | 100 ✅ |  |
| pickaladder/error_handlers.py | 80 ✅ | Type Safety Index 0% < 90% (-20) |
| pickaladder/extensions.py | 100 ✅ |  |
| pickaladder/constants.py | 100 ✅ |  |
| pickaladder/user/services.py | 70 ✅ | 1 Red ACL functions (-15), 3 Yellow ACL functions (-15) |
| pickaladder/user/models.py | 100 ✅ |  |
| pickaladder/user/forms.py | 100 ✅ |  |
| pickaladder/user/__init__.py | 100 ✅ |  |
| pickaladder/user/routes.py | 90 ✅ | 2 Yellow ACL functions (-10) |
| pickaladder/user/helpers.py | 100 ✅ |  |
| pickaladder/auth/forms.py | 80 ✅ | Type Safety Index 0% < 90% (-20) |
| pickaladder/auth/__init__.py | 100 ✅ |  |
| pickaladder/auth/routes.py | 70 ✅ | 2 Yellow ACL functions (-10), Type Safety Index 0% < 90% (-20) |
| pickaladder/auth/decorators.py | 80 ✅ | Type Safety Index 0% < 90% (-20) |
| pickaladder/tournament/services.py | 85 ✅ | 3 Yellow ACL functions (-15) |
| pickaladder/tournament/forms.py | 100 ✅ |  |
| pickaladder/tournament/__init__.py | 100 ✅ |  |
| pickaladder/tournament/utils.py | 95 ✅ | 1 Yellow ACL functions (-5) |
| pickaladder/tournament/routes.py | 95 ✅ | 1 Yellow ACL functions (-5) |
| pickaladder/teams/models.py | 80 ✅ | Type Safety Index 0% < 90% (-20) |
| pickaladder/teams/forms.py | 100 ✅ |  |
| pickaladder/teams/__init__.py | 100 ✅ |  |
| pickaladder/teams/utils.py | 80 ✅ | Type Safety Index 0% < 90% (-20) |
| pickaladder/teams/routes.py | 85 ✅ | 1 Red ACL functions (-15) |
| pickaladder/match/forms.py | 80 ✅ | Type Safety Index 0% < 90% (-20) |
| pickaladder/match/__init__.py | 100 ✅ |  |
| pickaladder/match/routes.py | 60 ❌ | 1 Red ACL functions (-15), 5 Yellow ACL functions (-25) |
| pickaladder/admin/__init__.py | 100 ✅ |  |
| pickaladder/admin/routes.py | 80 ✅ | Type Safety Index 0% < 90% (-20) |
| pickaladder/group/forms.py | 100 ✅ |  |
| pickaladder/group/__init__.py | 100 ✅ |  |
| pickaladder/group/utils.py | 35 ❌ | 3 Red ACL functions (-45), 4 Yellow ACL functions (-20) |
| pickaladder/group/routes.py | 75 ✅ | 1 Red ACL functions (-15), 2 Yellow ACL functions (-10) |

---
*Generated by Agent-Scorecard*