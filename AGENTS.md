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
*   **To run backend tests:** `make test`. **Important:** The application environment must be running before you can run the tests. Always run `make up` before running `make test`.
*   **To clean the Docker environment:** `docker-compose down -v`

*For more commands, see the `Makefile` and `README.md`.*

**Troubleshooting:**
*   **Docker Errors:** If you encounter Docker errors such as `permission denied` or `service "web" is not running`, try running the `make` commands with `sudo`. If you see a `429 Too Many Requests` error, it means Docker Hub is rate limiting anonymous pulls. There is no immediate workaround for this besides waiting.

## 4. Coding Standards and Contribution Guidelines

### General
*   **Python:** Follow PEP 8 style guidelines. All new functions should have docstrings.
*   **Commits:** Commit messages should follow the [conventional commit format](https://www.conventionalcommits.org/en/v1.0.0/).

### Linting, Formatting, and Static Analysis
Before submitting your changes, it is crucial to run all automated checks locally to ensure your code meets the project's quality standards. This will prevent CI failures.

Run the following commands from the root of the repository:

1.  **Linting:**
    ```bash
    ruff check .
    ```
2.  **Formatting Check:**
    ```bash
    ruff format --check .
    ```
3.  **Static Type Checking:**
    ```bash
    mypy .
    ```
4.  **Security Analysis:**
    ```bash
    bandit -r .
    ```

Please fix any errors reported by these tools before requesting a code review or submitting. You can often automatically fix linting and formatting issues by running `ruff check --fix .` and `ruff format .`.

### Business Logic
*   **Keep Routes Thin:** Route handlers in the `routes.py` files should be kept as "thin" as possible. Complex business logic should be encapsulated in separate utility functions or, for larger features, dedicated service classes.

### Database
*   **Use the ORM:** Use the SQLAlchemy ORM for all database interactions. The models are defined in `pickaladder/models.py`.
*   **Beware N+1 Queries:** When fetching lists of items that have related data, be mindful of the N+1 query problem. Use SQLAlchemy's relationship loading strategies (e.g., `joinedload`, `subqueryload`) to fetch all necessary data in a single, efficient query.
*   **Subquery Best Practices:** When using a subquery in an `IN` clause, you may see a `SAWarning: Coercing Subquery object into a select()`. To resolve this, explicitly call `.select()` on the subquery object (e.g., `filter(MyModel.id.in_(my_subquery.select()))`).

### Security
*   **CSRF Protection:** All forms and endpoints that perform state-changing actions (POST, PUT, DELETE requests) must be protected against Cross-Site Request Forgery (CSRF).
*   **Password Security:** Never handle passwords in plaintext. Use the provided `werkzeug.security` functions for hashing and checking passwords. Password reset functionality must use secure, single-use tokens.
*   **Input Validation:** All user-provided input must be validated on the server side before being used or stored.

## 5. Iterative Improvement and Documentation

*   **Iterative Problem Resolution:** If you encounter an issue (e.g., a security vulnerability, a bug, a confusing pattern), please look for other instances of the same problem in the codebase and address them.
*   **Update This File:** If you discover a new development technique, a useful debugging procedure, or a common pitfall, please update this `AGENTS.md` file to help future agents.
*   **Update Other Docs:** As you make changes, ensure that `REQUIREMENTS.md` and `DESIGN.md` (if applicable) are also updated to reflect the new state of the application.

## 6. Known Issues and Solutions

This section documents some of the issues that have been encountered in this project and their solutions.

### "Method Not Allowed" Error

*   **Symptom:** A "Method Not Allowed" error occurs when performing an action that should change the state of the application, such as accepting a friend request or logging in from the root page.
*   **Cause:** This error is caused by using a `GET` request (e.g., an `<a>` tag) for an action that requires a `POST` request.
*   **Solution:** Replace the `<a>` tag with a `<form>` that submits a `POST` request. Ensure that the form includes a CSRF token.

### CSRF Error

*   **Symptom:** A "CSRF Error: The CSRF token is missing" error occurs on form submission.
*   **Cause:** The form is missing a CSRF token.
*   **Solution:** Add a hidden input field with the CSRF token to the form. In this application, you can use `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`. For Javascript-generated forms, you can retrieve the token from a meta tag in the HTML head.

### Worker Timeout During Login

*   **Symptom:** The login process times out, and a "WORKER TIMEOUT" error is shown in the logs.
*   **Cause:** The password hashing function is using a very high number of iterations, which is too slow for the server.
*   **Solution:** Reduce the number of iterations in the `generate_password_hash` function. A value of `150000` is a reasonable choice. Also, implement a mechanism to re-hash the passwords of existing users on the fly when they log in.

### Pagination Error

*   **Symptom:** A `jinja2.exceptions.UndefinedError: 'pagination' is undefined` error occurs on pages with pagination.
*   **Cause:** The pagination template is not implemented as a reusable macro.
*   **Solution:** Refactor the pagination template into a macro that takes the `pagination` object and the `endpoint` as arguments. Update the call sites to use the macro correctly.

### Jinja2 TemplateSyntaxError in Macros

*   **Symptom:** A `jinja2.exceptions.TemplateSyntaxError: expected token 'name', got '**'` error occurs when defining a macro.
*   **Cause:** The version of Jinja2 used in this environment does not support the `**kwargs` syntax for accepting arbitrary keyword arguments directly in a macro's signature.
*   **Solution:** To create a flexible macro that accepts variable keyword arguments (e.g., for `url_for`), define the macro to accept a dictionary of parameters instead.
    *   **Incorrect:** `{% macro my_macro(param1, **kwargs) %}`
    *   **Correct:** `{% macro my_macro(param1, query_params={}) %}`
    *   Then, unpack the dictionary at the call site within the macro: `{{ url_for('my.endpoint', **query_params) }}`

### Note on `replace_with_git_merge_diff`

*   The `replace_with_git_merge_diff` tool automatically commits the changes it applies. Be mindful of this when working on multiple issues, as it can lead to a messy commit history. It's best to use this tool for a single, focused change and then submit it before moving on to the next task.
