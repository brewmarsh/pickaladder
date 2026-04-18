# Codebase Structure

**Analysis Date:** 2025-03-05

## Directory Layout

```
pickaladder/
├── .planning/          # GSD planning and documentation
├── nginx/              # Nginx configuration for production/beta
├── pickaladder/        # Main application package
│   ├── admin/          # Admin dashboard and management
│   ├── api/            # API endpoints (stats, etc.)
│   ├── auth/           # Authentication and registration
│   ├── base/           # Base classes (Repository)
│   ├── constants/      # Shared constants and messages
│   ├── core/           # Core types and foundational logic
│   ├── group/          # Group management and leaderboards
│   ├── main/           # Home, landing, and common pages
│   ├── match/          # Match recording and processing
│   ├── services/       # Shared business logic
│   ├── static/         # CSS, JS, and image assets
│   ├── teams/          # Team management
│   ├── templates/      # Jinja2 templates (shared and componentized)
│   ├── tournament/     # Tournament management
│   └── user/           # User profiles and settings
├── scripts/            # Database migrations and maintenance scripts
├── tests/              # Test suite (Unit, Integration, E2E)
├── app.py              # Application entry point
├── Dockerfile          # Container definition
├── pyproject.toml      # Build and dependency configuration
└── requirements.txt    # Python dependencies
```

## Directory Purposes

**pickaladder/[blueprint]/:**
- Purpose: Encapsulates logic for a specific domain.
- Contains: `routes.py`, `models.py`, `forms.py`, and a `services/` directory.
- Key files: `routes.py` (HTTP handlers), `services/` (domain logic).

**pickaladder/base/:**
- Purpose: Contains reusable base classes.
- Contains: `repository.py` for Firestore abstraction.
- Key files: `pickaladder/base/repository.py`.

**pickaladder/core/:**
- Purpose: Foundation types and constants.
- Contains: Type definitions and core constants.
- Key files: `pickaladder/core/types.py`, `pickaladder/core/constants.py`.

**pickaladder/templates/:**
- Purpose: Shared view layer.
- Contains: Global layout, component templates, and domain-specific subdirectories.
- Key files: `pickaladder/templates/base.html`.

**tests/:**
- Purpose: Quality assurance.
- Contains: Test modules grouped by functionality and E2E tests.
- Key files: `tests/conftest.py` (fixtures).

## Key File Locations

**Entry Points:**
- `app.py`: Flask application runner.
- `pickaladder/__init__.py`: App factory and extension initialization.

**Configuration:**
- `pickaladder/config.py`: Main configuration class.
- `pyproject.toml`: Tooling and dependency configuration.

**Core Logic:**
- `pickaladder/match/services/command.py`: Logic for recording matches.
- `pickaladder/user/services/core.py`: Core user-related logic.

**Testing:**
- `tests/`: All test files are located here, following the `test_*.py` naming pattern.

## Naming Conventions

**Files:**
- Blueprints: Directory name matches the domain (e.g., `match/`).
- Routes: Always `routes.py`.
- Services: Specific to function (e.g., `command.py`, `query.py`, `calculator.py`).

**Directories:**
- `services/`: Inside blueprints for domain-specific logic.
- `templates/`: Blueprint-specific templates are often nested in `pickaladder/templates/[domain]/` or `pickaladder/[domain]/templates/`.

## Where to Add New Code

**New Feature (e.g., "Leagues"):**
1. Create a new blueprint directory: `pickaladder/leagues/`.
2. Add `__init__.py`, `routes.py`, `models.py`, `forms.py`.
3. Create `pickaladder/leagues/services/` for business logic.
4. Register the blueprint in `pickaladder/__init__.py`.
5. Add templates to `pickaladder/templates/leagues/`.

**New Shared Utility:**
- Shared helper: `pickaladder/utils.py`.
- Shared service: `pickaladder/services/`.

**Tests:**
- Add a new `tests/test_leagues.py` or similar.

## Special Directories

**instance/:**
- Purpose: Local configuration and volatile data (e.g., SQLite for local tests, uploads).
- Generated: Yes.
- Committed: No.

**.planning/:**
- Purpose: GSD-specific project documentation and state tracking.
- Generated: Yes.
- Committed: Yes.

---

*Structure analysis: 2025-03-05*
