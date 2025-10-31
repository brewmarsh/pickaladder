# Contributing to Pickaladder

Thank you for contributing! This document provides the project-specific guidelines for architecture, code standards, and development.

**Please also read the `AGENTS.md` file** for rules on branch naming, commit messages, and general coding standards that apply to all repositories in this organization.

## 1. High-Level Architectural Overview

This is a monolithic web application built with **Flask**.
* **Backend:** Flask
* **Frontend:** Server-side rendered **Jinja2 templates**.
* **Database:** **PostgreSQL**
* **ORM:** **SQLAlchemy** (via the `Flask-SQLAlchemy` extension).

The Flask application is organized into blueprints. The main application is configured in `pickaladder/__init__.py`.

**IMPORTANT NOTE:** The `frontend/` directory contains a boilerplate React application that is **not currently used** by the main Flask app. All frontend work should be done in the `pickaladder/templates/` and `pickaladder/static/` directories.

## 2. Development Setup & Commands

### Prerequisites
* [Docker](https://www.docker.com/)
* [Docker Compose](https://docs.docker.com/compose/)
* [make](https://www.gnu.org/software/make/) (optional, but simplifies commands)

### Running the Application

1.  **Build and start all services:**
    ```bash
    make up
    ```
    The application will be available at `http://localhost:27272`.

2.  **Run backend tests:**
    **Important:** The application environment *must* be running (`make up`) before you can run the tests.
    ```bash
    make test
    ```

3.  **Run tests with coverage:**
    ```bash
    make coverage
    ```

4.  **Clean the Docker environment:**
    This will stop containers and remove all volumes (including the database).
    ```bash
    docker-compose down -v
    ```

### Troubleshooting
* **Database Issues:** If you encounter issues with the database, the cleanest way to reset is to run `docker-compose down -v` and then `make up`.
* **Docker Errors:** If you see `permission denied` or `service "web" is not running`, try running the `make` commands with `sudo`.
* **Docker Hub Rate Limit:** A `429 Too Many Requests` error means Docker Hub is rate-limiting anonymous pulls. There is no immediate workaround besides waiting.

## 3. Key Files and Directories

Review these files to understand the application's structure:

* `pickaladder/__init__.py`: The main Flask application factory. This is where the app is created, configured, and blueprints are registered.
* `init.sql`: The database schema. **This is the source of truth for the database structure.**
* `pickaladder/models.py`: Defines the SQLAlchemy database models.
* `pickaladder/auth/routes.py`: Handles user registration, login, and authentication.
* `pickaladder/user/routes.py`: Handles user profiles, friends, and other user-centric features.
* `pickaladder/match/routes.py`: Handles match creation and viewing the leaderboard.
* `pickaladder/admin/routes.py`: Handles administrative functions.
* `pickaladder/templates/`: Contains all Jinja2 HTML templates.
* `pickaladder/static/`: Contains static assets like CSS and images.
* `tests/`: Contains all tests.

## 4. Code Quality & Standards

### Quality Checks
Before submitting your code, please run the following checks. These are also enforced by our CI pipeline.

1.  **Linting and Formatting (Ruff):**
    This project uses `ruff` for both linting and formatting.
    ```bash
    ruff check --fix .
    ruff format .
    ```

2.  **Security Analysis (Bandit):**
    ```bash
    bandit -r .
    ```

3.  **Type Checking (Mypy):**
    This must be run inside the `web` container.
    ```bash
    docker compose exec web mypy .
    ```

### Business Logic
* **Keep Routes Thin:** Route handlers in `routes.py` files should be "thin." Complex business logic should be encapsulated in separate utility functions or service classes.
* **Separation of Concerns:** Organize code according to its purpose. Database interaction logic should be in a data access layer, business logic in a service layer, and presentation logic in routes/templates.

### Database
* **Use the ORM:** Use the SQLAlchemy ORM for all database interactions. Models are defined in `pickaladder/models.py`.
* **Database Migrations:** This project uses a simple, manual migration system. To make a schema change, create a new SQL file in the `migrations/` directory (e.g., `migrations/9_add_new_table.sql`). The `migrate.py` script runs these in order.
* **Beware N+1 Queries:** When fetching lists with related data, use SQLAlchemy's relationship loading strategies (e.g., `joinedload`, `subqueryload`) to avoid the N+1 query problem.
* **Subquery Best Practices:** When using a subquery in an `IN` clause, explicitly call `.select()` on the subquery object (e.g., `filter(MyModel.id.in_(my_subquery.select()))`) to avoid `SAWarning`.

### Security
* **CSRF Protection:** All forms and endpoints that perform state-changing actions (POST, PUT, DELETE) **must** be protected against CSRF.
* **Password Security:** Never handle passwords in plaintext. Use `werkzeug.security` functions for hashing and checking passwords.
* **Input Validation:** All user-provided input **must** be validated on the server side.

## 5. Known Issues & Solutions

This section documents common bugs and their required solutions.

* **Symptom:** "Method Not Allowed" error on an action (e.g., accepting a friend request).
    * **Cause:** Using an `<a>` tag (`GET` request) for an action that requires a `POST`.
    * **Solution:** Replace the `<a>` tag with a `<form>` that submits a `POST` request and includes a CSRF token.

* **Symptom:** "CSRF Error: The CSRF token is missing."
    * **Cause:** The form is missing a CSRF token.
    * **Solution:** Add `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">` to the form.

* **Symptom:** "WORKER TIMEOUT" error in logs during login.
    * **Cause:** The password hashing function (`generate_password_hash`) is using too many iterations, making it too slow.
    * **Solution:** Reduce the number of iterations to a reasonable value (e.g., `150000`). Implement on-the-fly password re-hashing for existing users when they log in.

* **Symptom:** `jinja2.exceptions.UndefinedError: 'pagination' is undefined`.
    * **Cause:** The pagination template is not implemented as a reusable macro.
    * **Solution:** Refactor the pagination template into a macro that takes the `pagination` object and `endpoint` as arguments.

* **Symptom:** `jinja2.exceptions.TemplateSyntaxError: expected token 'name', got '**'`.
    * **Cause:** This version of Jinja2 does not support `**kwargs` syntax in a macro's signature.
    * **Solution:** Define the macro to accept a dictionary of parameters (e.g., `query_params={}`) and unpack it at the call site within the macro (e.g., `{{ url_for('my.endpoint', **query_params) }}`).

## 6. Documentation
* **Iterative Improvement:** If you find a bug or confusing pattern, fix all other instances you find.
* **Update Docs:** As you make changes, ensure `REQUIREMENTS.md` and `DESIGN.md` (if applicable) are also updated.
* **Update This File:** If you discover a new development technique or common pitfall, please update this `CONTRIBUTING.md` file.
