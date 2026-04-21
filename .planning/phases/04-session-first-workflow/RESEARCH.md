# Phase 4: Session-First Workflow & Batch Recording - Research

**Researched:** 2024-10-24
**Domain:** Sports Session Management & Data Entry Optimization
**Confidence:** HIGH

## Summary

This phase introduces a "Session" as a top-level container for matches, specifically designed for high-frequency group play (e.g., pickleball sessions). The goal is to reduce recording friction from a multi-step search-and-select process to a "two-tap + score" workflow by pre-defining a player pool.

**Primary recommendation:** Implement `SessionService` as the orchestrator for session lifecycle and use a dedicated "Quick Log" view that maintains a persistent local state of the player pool to minimize re-selection.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Firebase Firestore | 7.2.0 | Data Storage | Primary database for pickaladder. |
| Flask | 3.1.3 | Web Framework | Existing application framework. |
| Flask-WTF | 1.2.2 | Form Handling | Standard for data validation in this project. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|--------------|
| mock-firestore | 0.11.0 | Testing | Used for unit testing Firestore interactions. |

**Installation:**
```bash
# Dependencies already in pyproject.toml
pip install .
```

## Architecture Patterns

### Recommended Project Structure
```
pickaladder/
├── group/
│   ├── services/
│   │   ├── session_service.py    # NEW: Logic for session lifecycle
│   ├── routes.py                 # Update: Session endpoints
├── match/
│   ├── services/
│   │   ├── command.py           # Update: record_match with session_id support
│   │   ├── record_service.py    # Update: Session-linked match queries
├── templates/
│   ├── group/
│   │   ├── quick_log.html       # NEW: High-contrast session UI
│   │   ├── session_view.html    # NEW: Session summary and verification
```

### Pattern 1: Session-First Match Recording
**What:** Matches are recorded as part of an active session.
**When to use:** For group play where the same 4-12 players are rotating.
**Implementation:** `Session` doc stores `playerIds`. `Match` doc stores `sessionId`.

### Anti-Patterns to Avoid
- **Hard-coding player pools:** Do not assume players don't change mid-session. Allow adding/removing players from the pool.
- **Synchronous ELO updates for batch:** If 10 matches are recorded at once, ensure the ELO calculation follows the correct sequence to maintain integrity.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Touch-optimized Grids | Custom CSS Flexbox | Bootstrap Grid + CSS Grid | Existing design system uses Bootstrap; consistency is key. |
| Date Math | Native JS/Python | `datetime` (Python) / `Date` (JS) | Simple enough for this use case, but keep timezones consistent (UTC). |

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Backend logic | ✓ | 3.13.11 | — |
| Pip | Package management | ✓ | 26.0.1 | — |
| Node/NPM | Frontend assets | ✓ | 24.11.0 / 11.11.0 | — |
| Firestore | Data storage | ✓ | 7.2.0 | — |

**Missing dependencies with no fallback:**
- None.

## Firestore Schema: `sessions`

| Field | Type | Description |
|-------|------|-------------|
| `groupId` | string | ID of the group the session belongs to. |
| `ownerId` | string | UID of the creator. |
| `playerIds` | array<string> | UIDs of players in the pool. |
| `matchIds` | array<string> | IDs of matches recorded. |
| `status` | string | `active` or `completed`. |
| `matchTypeDefault` | string | `singles` or `doubles`. |
| `createdAt` | timestamp | Server timestamp. |
| `updatedAt` | timestamp | Server timestamp. |
| `verifiedBy` | array<string> | UIDs of participants who approved the batch. |

## Batch Verification Logic

1. **Trigger:** A participant views the Session Summary and clicks "Approve All".
2. **Action:** UID is added to `sessions/{id}/verifiedBy`.
3. **Threshold Check:** If `len(verifiedBy) >= min_approvals` (default 2 or group-defined), the session is marked "Verified".
4. **Cascading Update:** All matches in `matchIds` are updated to `is_verified: true`.
5. **Stats Update:** Trigger any post-verification logic (e.g., DUPR sync, badge awards).

## Common Pitfalls

### Pitfall 1: Breaking Backward Compatibility in `MatchCommandService`
**What goes wrong:** Adding `session_id` to `MatchSubmission` as a required field breaks existing individual match recording and tournament logic.
**How to avoid:** Make `session_id` optional in the dataclass and service methods.

### Pitfall 2: Offline Sync Conflicts
**What goes wrong:** Multiple matches recorded offline with conflicting scores or player selections.
**How to avoid:** Use Firestore's `SERVER_TIMESTAMP` and implement client-side validation for player selection before submission.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | pyproject.toml |
| Quick run command | `pytest tests/test_match.py` |
| Full suite command | `pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BATCH-01 | Create session with pool | unit | `pytest tests/test_session_service.py` | ❌ Wave 0 |
| BATCH-02 | Match pre-populated from pool | integration | `pytest tests/test_quick_log.py` | ❌ Wave 0 |
| BATCH-03 | Winner-first scoring | unit | `pytest tests/test_match_command.py` | ✅ (Existing) |
| BATCH-05 | Batch verification | unit | `pytest tests/test_session_verification.py` | ❌ Wave 0 |

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V4 Access Control | yes | Verify session creation/access is restricted to group members. |
| V5 Input Validation | yes | Validate all `playerIds` exist and are part of the group. |

### Known Threat Patterns for Flask/Firestore

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Insecure Direct Object Reference (IDOR) | Broken Access | Verify `current_user` has permission for `groupId` and `sessionId`. |
| Data Tampering in Batch | Tampering | Check `is_verified` status before allowing further edits to session matches. |

## Sources

### Primary (HIGH confidence)
- `pickaladder/match/services/command.py` - Core match recording logic.
- `pickaladder/match/services/record_service.py` - Match query and stats logic.
- `pickaladder/templates/record_match.html` - Existing UI patterns.
- `.planning/research/BATCH_RECORDING.md` - UI/UX research on sessions.

### Secondary (MEDIUM confidence)
- `pyproject.toml` - Dependency versions and test config.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Core project tech.
- Architecture: HIGH - Follows existing service/repository pattern.
- Pitfalls: MEDIUM - Depends on implementation details of offline sync (if pursued).

**Research date:** 2024-10-24
**Valid until:** 2024-11-24
