# Agent Instructions

This document provides instructions for agents working on this project.

## Project Structure and Key Directories

*   `/`: The root directory contains the main application file (`app.py`), Docker-related files (`Dockerfile`, `docker-compose.yml`), and other configuration files.
*   `frontend/`: Contains the React-based frontend application.
*   `static/`: Contains static assets such as CSS and images.
*   `templates/`: Contains Flask templates for the web application.
*   `tests/`: Contains tests for the application.
*   `migrations/`: Contains database migration scripts.

## Build, Test, and Deployment Commands

*   **Build the Docker image:** `docker build . -t picka`
*   **Run the application:** `docker-compose up`
*   **Run tests:** `docker-compose exec web python -m pytest`

## Common Debugging Procedures and Tools

*   **Check application logs:** The application logs are streamed to the console when running `docker-compose up`. You can also view them with `docker-compose logs web`.
*   **Check database logs:** `docker-compose logs db`
*   **Docker build issues:** If a Docker build fails, try rebuilding with `DOCKER_BUILDKIT=0` for more verbose output to inspect the layers.
*   **Cleaning the environment:** To clean up the Docker environment, use `docker-compose down -v`.

## Coding Standards and Best Practices

*   **Python:** Follow PEP 8 style guidelines.
*   **Flask:** Use Blueprints for organizing routes.
*   **Error Handling:** Use `try-catch` blocks for database operations and other potentially failing code. Log errors to the console.

## Resource Optimization Guidelines

*   **Clear Docker cache:** If you are running low on disk space, you can clear the Docker build cache with `docker builder prune`.
*   **Clean npm cache:** For frontend-related issues, you can clean the npm cache with `npm cache clean --force`.

## Environment Variables

*   `POSTGRES_USER`: The username for the PostgreSQL database.
*   `POSTGRES_PASSWORD`: The password for the PostgreSQL database.
*   `POSTGRES_DB`: The name of the PostgreSQL database.
*   `MAIL_USERNAME`: The username for the email server.
*   `MAIL_PASSWORD`: The password for the email server.

## Input/Output Conventions

*   **API Responses:** API responses should be in JSON format.
*   **Code Coverage:** All new features should include corresponding unit tests with at least 80% code coverage.
=======
# Agent Guidelines

This document provides guidelines for agents working on this codebase.

## 1. Code Style

- All Python code must adhere to the PEP 8 style guide.
- Use a linter like `flake8` or `pylint` to check for style issues before submitting code.

## 2. Documentation

- All public functions and classes must have comprehensive docstrings that explain their purpose, arguments, and return values.
- Use the Google Python Style Guide for docstring formatting.

## 3. Configuration

- All configuration data must be validated using `voluptuous` schemas.
- Provide clear error messages for invalid configuration.

## 4. Constants

- All constants must be defined in `custom_components/meraki_ha/const.py`.
- Do not use magic strings or numbers in the code.

## 5. Testing

- All new features must be accompanied by unit tests.
- Run the entire test suite before submitting code to ensure that no regressions have been introduced.

## 6. Dependencies

- Use `dependabot` to keep dependencies up-to-date.
- Regularly review and update dependencies as needed.