# Agent Scorecard Report

**Target Agent Profile:** Standard Agent Readiness checks (ACL & Type Safety)
**Overall Score: 89.8/100** - PASS

✅ **Status: PASSED** - This codebase is Agent-Ready.

## 🎯 Top Refactoring Targets (Agent Cognitive Load (ACL))

ACL = Complexity + (Lines of Code / 20). Target: ACL <= 10.

| Function | File | ACL | Status |
|----------|------|-----|--------|
| `format_matches_for_dashboard` | `user/services/match_stats.py` | 38.0 | 🔴 Red |
| `create_app` | `__init__.py` | 24.9 | 🔴 Red |
| `get_latest_matches` | `match/services.py` | 24.2 | 🔴 Red |
| `register` | `auth/routes.py` | 22.2 | 🔴 Red |
| `record_match` | `match/services.py` | 22.0 | 🔴 Red |
| `get_candidate_player_ids` | `match/services.py` | 19.4 | 🔴 Red |
| `_record_match_batch` | `match/services.py` | 18.8 | 🔴 Red |
| `edit_tournament` | `tournament/routes.py` | 17.0 | 🔴 Red |
| `get_player_record` | `match/services.py` | 16.5 | 🔴 Red |
| `get_match_summary_context` | `match/services.py` | 16.4 | 🔴 Red |

## 🛡️ Type Safety Index

Target: >90% of functions must have explicit type signatures.

| File | Type Safety Index | Status |
| :--- | :---------------: | :----- |
| errors.py | 100% | ✅ |
| __init__.py | 100% | ✅ |
| utils.py | 100% | ✅ |
| error_handlers.py | 100% | ✅ |
| extensions.py | 100% | ✅ |
| constants.py | 100% | ✅ |
| context_processors.py | 100% | ✅ |
| user/models.py | 100% | ✅ |
| user/forms.py | 100% | ✅ |
| user/__init__.py | 100% | ✅ |
| user/routes.py | 100% | ✅ |
| user/helpers.py | 100% | ✅ |
| user/services/merging.py | 100% | ✅ |
| user/services/__init__.py | 100% | ✅ |
| user/services/profile.py | 100% | ✅ |
| user/services/core.py | 100% | ✅ |
| user/services/friendship.py | 100% | ✅ |
| user/services/activity.py | 100% | ✅ |
| user/services/match_stats.py | 100% | ✅ |
| user/services/dashboard.py | 100% | ✅ |
| auth/forms.py | 100% | ✅ |
| auth/__init__.py | 100% | ✅ |
| auth/routes.py | 100% | ✅ |
| auth/decorators.py | 100% | ✅ |
| tournament/services.py | 100% | ✅ |
| tournament/models.py | 100% | ✅ |
| tournament/forms.py | 100% | ✅ |
| tournament/__init__.py | 100% | ✅ |
| tournament/utils.py | 100% | ✅ |
| tournament/routes.py | 100% | ✅ |
| teams/services.py | 100% | ✅ |
| teams/models.py | 100% | ✅ |
| teams/forms.py | 100% | ✅ |
| teams/__init__.py | 100% | ✅ |
| teams/routes.py | 100% | ✅ |
| match/services.py | 100% | ✅ |
| match/models.py | 100% | ✅ |
| match/forms.py | 100% | ✅ |
| match/__init__.py | 100% | ✅ |
| match/routes.py | 100% | ✅ |
| admin/services.py | 100% | ✅ |
| admin/__init__.py | 100% | ✅ |
| admin/routes.py | 100% | ✅ |
| group/models.py | 100% | ✅ |
| group/forms.py | 100% | ✅ |
| group/__init__.py | 100% | ✅ |
| group/utils.py | 100% | ✅ |
| group/routes.py | 100% | ✅ |
| group/services/__init__.py | 100% | ✅ |
| group/services/leaderboard.py | 100% | ✅ |
| group/services/stats.py | 100% | ✅ |
| group/services/group_service.py | 100% | ✅ |
| group/services/match_parser.py | 100% | ✅ |
| core/__init__.py | 100% | ✅ |
| core/types.py | 100% | ✅ |
| core/constants.py | 100% | ✅ |
| main/__init__.py | 100% | ✅ |
| main/routes.py | 100% | ✅ |

## 🤖 Agent Prompts for Remediation (CRAFT Format)

### File: `__init__.py` - High Cognitive Load
> **Context**: You are a Senior Python Engineer focused on code maintainability.
> **Request**: Refactor functions in `__init__.py` with Red ACL scores.
> **Actions**:
> - Target functions: `create_app`.
> - Extract nested logic into smaller helper functions.
> - Ensure all units result in an ACL score < 10.
> **Frame**: Keep functions under 50 lines. Ensure all tests pass.
> **Template**: Markdown code blocks for the refactored code.

### File: `user/services/match_stats.py` - High Cognitive Load
> **Context**: You are a Senior Python Engineer focused on code maintainability.
> **Request**: Refactor functions in `user/services/match_stats.py` with Red ACL scores.
> **Actions**:
> - Target functions: `format_matches_for_dashboard`, `get_recent_opponents`.
> - Extract nested logic into smaller helper functions.
> - Ensure all units result in an ACL score < 10.
> **Frame**: Keep functions under 50 lines. Ensure all tests pass.
> **Template**: Markdown code blocks for the refactored code.

### File: `auth/routes.py` - High Cognitive Load
> **Context**: You are a Senior Python Engineer focused on code maintainability.
> **Request**: Refactor functions in `auth/routes.py` with Red ACL scores.
> **Actions**:
> - Target functions: `register`.
> - Extract nested logic into smaller helper functions.
> - Ensure all units result in an ACL score < 10.
> **Frame**: Keep functions under 50 lines. Ensure all tests pass.
> **Template**: Markdown code blocks for the refactored code.

### File: `tournament/routes.py` - High Cognitive Load
> **Context**: You are a Senior Python Engineer focused on code maintainability.
> **Request**: Refactor functions in `tournament/routes.py` with Red ACL scores.
> **Actions**:
> - Target functions: `edit_tournament`.
> - Extract nested logic into smaller helper functions.
> - Ensure all units result in an ACL score < 10.
> **Frame**: Keep functions under 50 lines. Ensure all tests pass.
> **Template**: Markdown code blocks for the refactored code.

### File: `match/services.py` - High Cognitive Load
> **Context**: You are a Senior Python Engineer focused on code maintainability.
> **Request**: Refactor functions in `match/services.py` with Red ACL scores.
> **Actions**:
> - Target functions: `_record_match_batch`, `record_match`, `get_candidate_player_ids`, `get_player_record`, `get_latest_matches`, `get_match_summary_context`.
> - Extract nested logic into smaller helper functions.
> - Ensure all units result in an ACL score < 10.
> **Frame**: Keep functions under 50 lines. Ensure all tests pass.
> **Template**: Markdown code blocks for the refactored code.

### File: `match/routes.py` - High Cognitive Load
> **Context**: You are a Senior Python Engineer focused on code maintainability.
> **Request**: Refactor functions in `match/routes.py` with Red ACL scores.
> **Actions**:
> - Target functions: `edit_match`.
> - Extract nested logic into smaller helper functions.
> - Ensure all units result in an ACL score < 10.
> **Frame**: Keep functions under 50 lines. Ensure all tests pass.
> **Template**: Markdown code blocks for the refactored code.


### 📂 Full File Analysis

| File | Score | Issues |
| :--- | :---: | :--- |
| errors.py | 100 ✅ |  |
| __init__.py | 78 ✅ | Bloated File: 270 lines (-7), 1 Red ACL functions (-15) |
| utils.py | 100 ✅ |  |
| error_handlers.py | 100 ✅ |  |
| extensions.py | 100 ✅ |  |
| constants.py | 100 ✅ |  |
| context_processors.py | 95 ✅ | 1 Yellow ACL functions (-5) |
| user/models.py | 100 ✅ |  |
| user/forms.py | 100 ✅ |  |
| user/__init__.py | 100 ✅ |  |
| user/routes.py | 97 ✅ | Bloated File: 233 lines (-3) |
| user/helpers.py | 100 ✅ |  |
| user/services/merging.py | 90 ✅ | 2 Yellow ACL functions (-10) |
| user/services/__init__.py | 99 ✅ | Bloated File: 212 lines (-1) |
| user/services/profile.py | 100 ✅ |  |
| user/services/core.py | 92 ✅ | Bloated File: 237 lines (-3), 1 Yellow ACL functions (-5) |
| user/services/friendship.py | 100 ✅ |  |
| user/services/activity.py | 81 ✅ | Bloated File: 293 lines (-9), 2 Yellow ACL functions (-10) |
| user/services/match_stats.py | 51 ❌ | Bloated File: 394 lines (-19), 2 Red ACL functions (-30) |
| user/services/dashboard.py | 100 ✅ |  |
| auth/forms.py | 100 ✅ |  |
| auth/__init__.py | 100 ✅ |  |
| auth/routes.py | 72 ✅ | Bloated File: 281 lines (-8), 1 Red ACL functions (-15), 1 Yellow ACL functions (-5) |
| auth/decorators.py | 100 ✅ |  |
| tournament/services.py | 42 ❌ | Bloated File: 688 lines (-48), 2 Yellow ACL functions (-10) |
| tournament/models.py | 100 ✅ |  |
| tournament/forms.py | 100 ✅ |  |
| tournament/__init__.py | 100 ✅ |  |
| tournament/utils.py | 95 ✅ | 1 Yellow ACL functions (-5) |
| tournament/routes.py | 62 ❌ | Bloated File: 387 lines (-18), 1 Red ACL functions (-15), 1 Yellow ACL functions (-5) |
| teams/services.py | 92 ✅ | Bloated File: 230 lines (-3), 1 Yellow ACL functions (-5) |
| teams/models.py | 100 ✅ |  |
| teams/forms.py | 100 ✅ |  |
| teams/__init__.py | 100 ✅ |  |
| teams/routes.py | 100 ✅ |  |
| match/services.py | 0 ❌ | Bloated File: 796 lines (-59), 6 Red ACL functions (-90) |
| match/models.py | 100 ✅ |  |
| match/forms.py | 100 ✅ |  |
| match/__init__.py | 100 ✅ |  |
| match/routes.py | 75 ✅ | 1 Red ACL functions (-15), 2 Yellow ACL functions (-10) |
| admin/services.py | 100 ✅ |  |
| admin/__init__.py | 100 ✅ |  |
| admin/routes.py | 83 ✅ | Bloated File: 320 lines (-12), 1 Yellow ACL functions (-5) |
| group/models.py | 100 ✅ |  |
| group/forms.py | 100 ✅ |  |
| group/__init__.py | 100 ✅ |  |
| group/utils.py | 58 ❌ | Bloated File: 523 lines (-32), 2 Yellow ACL functions (-10) |
| group/routes.py | 78 ✅ | Bloated File: 373 lines (-17), 1 Yellow ACL functions (-5) |
| group/services/__init__.py | 100 ✅ |  |
| group/services/leaderboard.py | 91 ✅ | Bloated File: 290 lines (-9) |
| group/services/stats.py | 95 ✅ | 1 Yellow ACL functions (-5) |
| group/services/group_service.py | 57 ❌ | Bloated File: 586 lines (-38), 1 Yellow ACL functions (-5) |
| group/services/match_parser.py | 95 ✅ | 1 Yellow ACL functions (-5) |
| core/__init__.py | 100 ✅ |  |
| core/types.py | 100 ✅ |  |
| core/constants.py | 100 ✅ |  |
| main/__init__.py | 100 ✅ |  |
| main/routes.py | 100 ✅ |  |

---
*Generated by Agent-Scorecard*