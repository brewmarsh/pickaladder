# Phase 7: Group & Team Foundation Refactor - Research

**Researched:** 2026-04-21
**Domain:** Firestore Repository Pattern, Schema Standardization
**Confidence:** HIGH

## Summary

This phase focuses on standardizing the data access layer and entity schemas for Groups and Teams. Currently, Firestore interactions are scattered across static methods in service classes, leading to duplication (especially in Team creation) and inconsistent field naming (e.g., `createdAt` vs `created_at`). 

The research confirms that `createdAt` (camelCase) is the dominant pattern in the codebase (~90%), with `teams` and `group_invites` being the primary outliers using `created_at`. A new `BaseRepository` will be extracted to provide standardized CRUD operations, batch fetching, and automatic timestamp management.

**Primary recommendation:** Standardize all Firestore documents to use `createdAt` and `updatedAt` (camelCase) and migrate existing data in the `teams` and `group_invites` collections.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| firebase-admin | 7.3.0 | Firestore SDK | Official SDK for server-side Firebase interaction. [VERIFIED: pyproject.toml] |
| pydantic | 2.12.5 | Data Validation | Used for structured data models and validation. [VERIFIED: pyproject.toml] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| mock-firestore | 0.11.0 | Testing | Mocking Firestore for unit tests. [VERIFIED: pyproject.toml] |

## Architecture Patterns

### Recommended Project Structure
```
pickaladder/
├── base/
│   └── repository.py    # BaseRepository definition
├── group/
│   ├── repository.py    # GroupRepository (new)
│   └── services/
│       └── group_service.py # Refactored to use repository
└── teams/
    ├── repository.py    # TeamRepository (new)
    └── services.py      # Refactored to use repository
```

### Pattern 1: Repository Pattern
**What:** Decouples the service layer from the data access layer (Firestore).
**When to use:** All database interactions.
**Example:**
```python
# Proposed GroupRepository
class GroupRepository(BaseRepository):
    COLLECTION_NAME = "groups"

    @classmethod
    def get_user_groups(cls, db, user_id):
        user_ref = db.collection("users").document(user_id)
        return cls.query(db, filters=[("members", "array_contains", user_ref)])
```

### Anti-Patterns to Avoid
- **Mixed Timestamps:** Do not use `created_at` in some collections and `createdAt` in others. [VERIFIED: Architectural Audit]
- **Business Logic in Repositories:** Keep ELO calculations and complex enrichment in Services; Repositories should return raw or lightly structured data.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| ID Enrichment | Manual `data['id'] = doc.id` | `BaseRepository` helper | Repetitive and error-prone. |
| Batch Fetching | Loop with `.get()` | `db.get_all(refs)` | Significantly more efficient (single round trip). |
| Timestamping | Manual `SERVER_TIMESTAMP` | `BaseRepository` hooks | Ensures consistency across all creations/updates. |

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `teams` collection uses `created_at` | Data migration script to rename to `createdAt`. |
| Stored data | `group_invites` collection uses `created_at` | Data migration script to rename to `createdAt`. |
| Secrets/env vars | `FirestoreDocument` TypedDict in `core/types.py` | Code edit to change `created_at` to `createdAt`. |

**Nothing found in category:** Live service config, OS-registered state, Build artifacts.

## Common Pitfalls

### Pitfall 1: Sorting Inconsistency
**What goes wrong:** Queries fail or return wrong results when sorting by a field that isn't present on all documents.
**Why it happens:** Some documents have `createdAt`, others have `created_at`.
**How to avoid:** Standardize field names and run a migration script before updating code that queries/sorts.

### Pitfall 2: Team Duplication
**What goes wrong:** Multiple teams created for the same two players.
**Why it happens:** Logic for sorting member IDs before querying is duplicated and slightly different in `models.py` and `services.py`.
**How to avoid:** Centralize `get_or_create_team` logic in `TeamRepository` and ensure member IDs are always sorted alphabetically.

## Code Examples

### Standardized BaseRepository (Proposed)
```python
class BaseRepository:
    COLLECTION_NAME: str = ""

    @classmethod
    def _enrich(cls, doc_snap):
        if not doc_snap.exists: return None
        data = doc_snap.to_dict() or {}
        data["id"] = doc_snap.id
        return data

    @classmethod
    def create(cls, db, data):
        from firebase_admin import firestore
        data["createdAt"] = firestore.SERVER_TIMESTAMP
        _, ref = db.collection(cls.COLLECTION_NAME).add(data)
        return ref.id

    @classmethod
    def update(cls, db, doc_id, data):
        from firebase_admin import firestore
        data["updatedAt"] = firestore.SERVER_TIMESTAMP
        db.collection(cls.COLLECTION_NAME).document(doc_id).update(data)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `created_at` | `createdAt` | Phase 7 | Uniformity across Firestore documents. |
| Static Service Methods | Repository Classes | Phase 7 | Improved testability and separation of concerns. |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `createdAt` is the preferred casing for the project. | Summary | Minimal; but if `created_at` was intended, many more files need updating. |
| A2 | No external services rely on the specific casing of `created_at` in Firestore. | Runtime State | Low; Firestore is mostly internal to the app. |

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Core Runtime | ✓ | 3.13.11 | — |
| pip | Package Manager | ✓ | 26.0.1 | — |
| pytest | Testing | ✓ | 9.0.2 | — |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | pyproject.toml |
| Quick run command | `pytest tests/test_group.py tests/test_team_service.py` |
| Full suite command | `pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REQ-01 | Standardized timestamps | Unit | `pytest tests/test_group.py` | ✅ |
| REQ-02 | Consolidated creation logic | Unit | `pytest tests/test_team_service.py` | ✅ |
| REQ-03 | Repository Pattern | Unit | `pytest tests/test_group.py` | ✅ |

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | Centralized validation in Repositories/Services (e.g., MatchValidationService). |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Insecure Direct Object Reference (IDOR) | Tampering | Ensure `user_id` or `is_admin` checks are performed in services before calling Repository updates. |

## Sources

### Primary (HIGH confidence)
- Codebase audit of `pickaladder/group/services/group_service.py` and `pickaladder/teams/`.
- Grep search for timestamp patterns across `pickaladder/`.
- Official Firestore documentation (training data + codebase patterns).

### Secondary (MEDIUM confidence)
- `.planning/research/GROUP_TEAM_REFACTOR.md` - Used as a baseline for architectural decisions.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Verified in pyproject.toml.
- Architecture: HIGH - Based on established patterns and existing MatchCommandService.
- Pitfalls: HIGH - Directly observed in the current codebase.

**Research date:** 2026-04-21
**Valid until:** 2026-05-21
