# Agent Instructions

This document provides instructions for agents working on this project. By following these guidelines, you can contribute effectively and maintain the quality of the codebase.

## 1. High-Level Architectural Overview

This is a monolithic web application built with **Flask**. The frontend is rendered server-side using **Jinja2 templates**. The application uses **Google Firebase** for its backend services: **Firebase Authentication** for user management, **Cloud Firestore** as the NoSQL database, and **Firebase Storage** for file storage.

The Flask application is organized into blueprints. The main application is configured in `pickaladder/__init__.py`.

**IMPORTANT NOTE:** The `frontend/` directory contains a boilerplate React application that is **not currently used** by the main Flask app. All frontend work should be done in the `pickaladder/templates/` and `pickaladder/static/` directories.

## 2. Key Files and Directories

When getting started, it's helpful to review these key files to understand the application's structure and logic.

*   `pickaladder/__init__.py`: The main Flask application factory. This is where the app is created and configured, and blueprints are registered.
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

### Version Control
*   **Branching:** Create a new branch for each new feature or fix. Use the following naming conventions:
    *   `feature/<branch-description>` for new features (e.g., `feature/add-user-profile`)
    *   `fix/<branch-description>` for bug fixes (e.g., `fix/login-form-validation`)

### Repository Badges
The `README.md` file should include a set of badges to provide at-a-glance information about the project. The following badges are recommended:

*   **CI Status:** Shows the status of the CI build.
*   **Code Coverage:** Shows the test coverage percentage.
*   **License:** Displays the project's open-source license.
*   **Python Version:** Indicates the supported Python version.
*   **Code Style:** Shows the code formatting standard being used.
*   **Vulnerability Scan:** Displays the status of the vulnerability scan.

### Code Quality Checks
Before submitting your code, please run the following checks to ensure code quality and prevent regressions.

*   **Linting and Formatting:** This project uses `ruff` for both linting and formatting. Run the following commands to automatically fix most issues:
    ```bash
    ruff check --fix .
    ruff format .
    ```
*   **Security Analysis:** This project uses `bandit` to find common security issues.
    ```bash
    bandit -r .
    ```
*   **Vulnerability Scanning:** This project uses `trivy` to scan for vulnerabilities in the application and its dependencies. This is run in the CI pipeline, but you can also run it locally.

*   **Type Checking:** This project uses `mypy` for static type checking. Run the following command from the root of the repository to check for type errors. Note that this must be run inside the `web` container.
    ```bash
    docker compose exec web mypy .
    ```

*   **Test Coverage:** This project uses `coverage` to measure test coverage. Run the following command to run the tests and generate a coverage report.
    ```bash
    make coverage
    ```

### Business Logic
*   **Keep Routes Thin:** Route handlers in the `routes.py` files should be kept as "thin" as possible. Complex business logic should be encapsulated in separate utility functions or, for larger features, dedicated service classes.
*   **Separation of Concerns:** Ensure that code is organized according to its purpose. For example, database interaction logic should be in a data access layer, business logic in a service layer, and presentation logic in the routes and templates. Refactor code that violates this principle.

### Database
*   **Firestore:** The application uses Google Cloud Firestore as its NoSQL database.
*   **Data Models:** While Firestore is schema-less, the application generally follows a structured data model.
*   **Batch Operations:** Use batch writes when updating multiple documents to ensure atomicity.
*   **Indexing:** Be mindful of query requirements. Firestore requires composite indexes for complex queries involving multiple fields or sorting orders.

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
