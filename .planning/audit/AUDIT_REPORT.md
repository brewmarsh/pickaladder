# Audit Report: pickaladder

This report documents the findings of the Firestore and Codebase audits conducted as part of Phase 1: Quality Foundation.

## Firestore Audit (AUDIT-03)

### Current Data Models
* **Users:** Contains profile info, roles, and denormalized stats (`stats.wins`, `stats.losses`, `stats.elo`).
* **Matches:** Stores match results, participants, and denormalized player snapshots.
* **Tournaments/Groups:** Manage event and social structures.
* **Settings:** Global configuration document.

### Efficiency and Performance
* **CRITICAL ISSUE:** `MatchRecordService.get_leaderboard_data` streams **ALL** users and then streams **ALL** matches for each user to calculate stats. This is an $O(U \cdot M)$ operation that will fail as the database grows.
* **Inefficient Friend Checks:** `search_users` streams a user's entire `friends` subcollection to check status, which is inefficient for social-heavy users.
* **Redundant Fields:** Data model fragmentation exists (e.g., `duprRating` vs `dupr_rating`), requiring double updates and increasing storage/complexity.
* **N+1 Potential:** Some administrative and generation tasks perform multiple sequential writes/reads instead of using batches or transactions where possible.

### Query Patterns and Indexes
* **Missing Indexes:** Some complex queries (e.g., ordering by `createdAt` with filters) may fail or be slow if matching composite indexes aren't defined beyond what's in `firestore.indexes.json`.
* **Aggregation Success:** Admin stats correctly use server-side `count()` aggregations.

## Codebase Review (AUDIT-01)

### Architecture and Consistency
* **Service Layer Inconsistency:** The `match` service is highly modular and well-structured, whereas the `admin` and `user` services have significant logic overlap and mix transport concerns (forms) with business logic.
* **Inconsistent DB Access:** `firestore.client()` is called redundantly across routes and services instead of being managed by a central provider or app context.
* **Modularization:** Blueprints are used effectively for feature separation.

### Security Assessment
* **CRITICAL VULNERABILITY:** The `admin.generate_users` route in `pickaladder/admin/routes.py` is missing the `@login_required(admin_required=True)` decorator. This allows **unauthenticated** users to flood the database with fake accounts and data.
* **PII/Secret Leakage:** `pickaladder/__init__.py` contains debug logging (`_configure_mail_logging`) that prints mail server details and password lengths to stderr. While not the full password, this is poor practice.
* **Impersonation Risk:** The impersonation feature is powerful and must be rigorously protected. Currently, it relies on session-side `is_admin` which could be a target for session tampering if not handled securely by the framework.

### Technical Debt
* **Overlapping Logic:** Multiple profile update paths (`update_settings`, `update_dashboard_profile`, etc.) lead to "DRY" violations and maintenance overhead.
* **Hardcoded Values:** Several routes and services contain hardcoded constants (e.g., storage buckets, minimum user counts) that should be moved to a centralized configuration (AUDIT-02).
* **Missing Type Safety:** While some `TYPE_CHECKING` is used, the project lacks comprehensive `mypy` enforcement (QUAL-01).
