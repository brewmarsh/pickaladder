# Architecture

**Analysis Date:** 2025-03-05

## Pattern Overview

**Overall:** Modular Monolith using Flask Blueprints

**Key Characteristics:**
- **Blueprint-based modularity**: Each domain (auth, user, match, tournament, group, teams) is encapsulated in a Flask Blueprint.
- **Service-Oriented Logic**: Business logic is decoupled from routes and placed into service classes, often separated into Command and Query responsibilities.
- **Repository Pattern**: Data access to Firestore is abstracted through repository classes inheriting from `BaseRepository`.

## Layers

**Presentation Layer:**
- Purpose: Handles HTTP requests, renders templates, and manages user sessions.
- Location: `pickaladder/[blueprint]/routes.py` and `pickaladder/templates/`
- Contains: Flask route handlers, Jinja2 templates, and Flask-WTF forms.
- Depends on: Service Layer, Core types.
- Used by: Web browsers/End users.

**Service Layer:**
- Purpose: Implements business logic and coordinates domain operations.
- Location: `pickaladder/[blueprint]/services/`
- Contains: Command services (writes), Query services (reads), calculators, and validators.
- Depends on: Repository Layer, Core types, external SDKs (Firebase).
- Used by: Presentation Layer.

**Data Access Layer (Repository):**
- Purpose: Abstracts Firestore CRUD operations.
- Location: `pickaladder/base/repository.py` and blueprint-specific service classes inheriting from `BaseRepository`.
- Contains: Logic for interacting with Firebase Firestore.
- Depends on: Firebase Admin SDK.
- Used by: Service Layer.

## Data Flow

**Match Submission Flow:**

1. **User Input**: User submits a match form via `pickaladder/match/routes.py`.
2. **Validation**: Route calls `MatchCommandService.record_match` which uses `MatchValidationService` to validate data.
3. **Processing**: `MatchCommandService` prepares Firestore document data and calculates stats using `MatchStatsCalculator`.
4. **Persistence**: `MatchCommandService` uses a Firestore batch to write the match record and update related statistics (user ratings, streaks).
5. **Response**: Route redirects the user or displays a success message.

**State Management:**
- **Client-side**: Flask-Login and server-side sessions manage authentication state.
- **Server-side**: Firebase Firestore acts as the source of truth for all application state (users, matches, tournaments).

## Key Abstractions

**BaseRepository:**
- Purpose: Provides standardized CRUD operations for Firestore documents.
- Examples: `pickaladder/base/repository.py`
- Pattern: Repository Pattern.

**MatchCommandService / MatchQueryService:**
- Purpose: Separates write operations (commands) from read operations (queries).
- Examples: `pickaladder/match/services/command.py`, `pickaladder/match/services/query.py`
- Pattern: CQRS (Command Query Responsibility Segregation) light.

**Wrapper Models:**
- Purpose: Provide helper methods on top of raw Firestore dictionaries for use in templates.
- Examples: `pickaladder/match/models.py` (Match class), `pickaladder/user/models.py` (UserSession class).

## Entry Points

**Web Application:**
- Location: `app.py`
- Triggers: WSGI server (Gunicorn/Waitress) or direct execution for development.
- Responsibilities: Initializes the Flask app via `pickaladder.create_app()`, registers blueprints, and starts the server.

**Firebase Initialization:**
- Location: `pickaladder/__init__.py` (`_initialize_firebase` function)
- Triggers: App startup.
- Responsibilities: Configures the Firebase Admin SDK using credentials from environment variables or local JSON files.

## Error Handling

**Strategy:** Centralized error handling using Flask error handlers.

**Patterns:**
- **Blueprint-level error handlers**: Defined in `pickaladder/error_handlers.py`.
- **Validation Exceptions**: Services raise exceptions which are caught by routes to display flash messages.

## Cross-Cutting Concerns

**Logging:** Standard Python logging, configured during app initialization in `pickaladder/__init__.py`.
**Validation:** Flask-WTF for form validation and custom Service-level validation (e.g., `MatchValidationService`).
**Authentication:** Flask-Login for session management, integrated with Firestore in `pickaladder/__init__.py`.

---

*Architecture analysis: 2025-03-05*
