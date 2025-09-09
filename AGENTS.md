# Agent Instructions

This document provides instructions for agents working on this project. By following these guidelines, you can contribute effectively and maintain the quality of the codebase.

## 1. High-Level Architectural Overview

This is a monolithic web application built with **Flask**. The frontend is rendered server-side using **Jinja2 templates**. The application uses a **PostgreSQL** database and the **SQLAlchemy ORM** (via the `Flask-SQLAlchemy` extension).

The Flask application is organized into blueprints. The main application is configured in `pickaladder/__init__.py`.

**IMPORTANT NOTE:** The `frontend/` directory contains a boilerplate React application that is **not currently used** by the main Flask app. All frontend work should be done in the `pickaladder/templates/` and `pickaladder/static/` directories.

## 2. Key Files and Directories

When getting started, it's helpful to review these key files to understand the application's structure and logic.

*   `pickaladder/__init__.py`: The main Flask application factory. This is where the app is created and configured, and blueprints are registered.
*   `init.sql`: The database schema. This is the source of truth for the database structure.
*   `pickaladder/models.py`: Defines the SQLAlchemy database models.
*   `pickaladder/auth/routes.py`: Handles user registration, login, and authentication logic.
*   `pickaladder/user/routes.py`: Handles user profiles, friends, and other user-centric features.
*   `pickaladder/match/routes.py`: Handles match creation and viewing the leaderboard.
*   `pickaladder/admin/routes.py`: Handles administrative functions.
*   `pickaladder/templates/`: Contains all Jinja2 HTML templates.
*   `pickaladder/static/`: Contains static assets like CSS and images.
*   `tests/`: Contains tests for the application.

## 3. Build, Test, and Deployment

*   **To build and start the application:** `make up`
*   **To run backend tests:** `make test`
*   **To clean the Docker environment:** `docker-compose down -v`

*For more commands, see the `Makefile` and `README.md`.*

## 4. Coding Standards and Contribution Guidelines

### General
*   **Python:** Follow PEP 8 style guidelines. All new functions should have docstrings.
*   **Commits:** Commit messages should follow the [conventional commit format](https://www.conventionalcommits.org/en/v1.0.0/).

### Linting and Formatting
*   **Ruff:** This project uses `ruff` for both linting and formatting, replacing `flake8` and `black`. Before submitting, please run `ruff check --fix .` and `ruff format .` to ensure your code is compliant. The CI pipeline will fail if there are linting errors.

### Business Logic
*   **Keep Routes Thin:** Route handlers in the `routes.py` files should be kept as "thin" as possible. Complex business logic should be encapsulated in separate utility functions or, for larger features, dedicated service classes.

### Database
*   **Use the ORM:** Use the SQLAlchemy ORM for all database interactions. The models are defined in `pickaladder/models.py`.
*   **Beware N+1 Queries:** When fetching lists of items that have related data, be mindful of the N+1 query problem. Use SQLAlchemy's relationship loading strategies (e.g., `joinedload`, `subqueryload`) to fetch all necessary data in a single, efficient query.

### Security
*   **CSRF Protection:** All forms and endpoints that perform state-changing actions (POST, PUT, DELETE requests) must be protected against Cross-Site Request Forgery (CSRF).
*   **Password Security:** Never handle passwords in plaintext. Use the provided `werkzeug.security` functions for hashing and checking passwords. Password reset functionality must use secure, single-use tokens.
*   **Input Validation:** All user-provided input must be validated on the server side before being used or stored.

## 5. Iterative Improvement and Documentation

*   **Iterative Problem Resolution:** If you encounter an issue (e.g., a security vulnerability, a bug, a confusing pattern), please look for other instances of the same problem in the codebase and address them.
*   **Update This File:** If you discover a new development technique, a useful debugging procedure, or a common pitfall, please update this `AGENTS.md` file to help future agents.
*   **Update Other Docs:** As you make changes, ensure that `REQUIREMENTS.md` and `DESIGN.md` (if applicable) are also updated to reflect the new state of the application.
