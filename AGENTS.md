# Agent Instructions

This document provides instructions for agents working on this project.

## Project Structure and Key Directories

*   `/`: The root directory contains the main application file (`app.py`), Docker-related files (`Dockerfile`, `docker-compose.yml`), and other configuration files.
*   `frontend/`: Contains the React-based frontend application.
    *   `frontend/src/`: Contains the React source code.
    *   `frontend/public/`: Contains the public assets for the frontend.
*   `static/`: Contains static assets such as CSS and images.
*   `templates/`: Contains Flask templates for the web application.
*   `tests/`: Contains tests for the application.
*   `migrations/`: Contains database migration scripts.

## Build, Test, and Deployment Commands

*   **To install dependencies:** `make build`
*   **To run the application:** `make up`
*   **To run backend tests:** `make test`
*   **To run frontend tests:** `npm test --prefix frontend`
*   **To build the project:** `docker compose build`
*   **To start local services:** `docker compose up --build -d`

## Common Debugging Procedures and Tools

*   **Check application logs:** When debugging API issues, first check `app.log` for application-level errors.
*   **Check container logs:** For Docker container issues, use `docker logs [container_name]` to retrieve logs.
*   **Verbose Docker builds:** If a Docker build fails, consider rebuilding with `DOCKER_BUILDKIT=0` for more verbose output to inspect layers.
*   **Cleaning the environment:** To clean up the Docker environment, use `docker-compose down -v`.

## Coding Standards and Best Practices

*   **Python:** Follow PEP 8 style guidelines. All new functions should have docstrings. Before checking in any code, please run `black .` and `flake8 .` to format and lint the code.
*   **React:** All React components should be functional components.
*   **Error Handling:** Use centralized `try-catch` blocks and log to `console.error`.
*   **Refactoring:** Prefer `const` over `let` where variable reassignment is not needed.

## Resource Optimization Guidelines

*   **Clear Docker cache:** If you are running low on disk space, you can clear the Docker build cache with `docker builder prune`.
*   **Clean npm cache:** Before running large builds, execute `npm cache clean --force` to free up disk space in the VM.

## Environment Variables

*   `POSTGRES_USER`: The username for the PostgreSQL database.
*   `POSTGRES_PASSWORD`: The password for the PostgreSQL database.
*   `POSTGRES_DB`: The name of the PostgreSQL database.
*   `MAIL_SERVER`: The hostname or IP address of the email server.
*   `MAIL_PORT`: The port of the email server.
*   `MAIL_USERNAME`: The username for the email server.
*   `MAIL_PASSWORD`: The password for the email server.
*   `API_BASE_URL`: The base URL for the API. Default value: `http://localhost:27272/api`.

## Input/Output Conventions

*   **API Responses:** API responses should be in JSON format.
*   **Code Coverage:** All new features should include corresponding unit tests with at least 80% code coverage.
*   **Commit Messages:** Commit messages should follow the conventional commit format.

## Iterative Problem Resolution

Agents should iteratively resolve similar problems. For example, if there is an error in a single file regarding indentation, agents should examine all files for similar issues, starting with those files closest in the folder structure. Then agents should continuously update the agents.md file with their findings on how to further avoid similar problems.

## Closed Loop Documentation

Agents must update any documentation as they make changes to code, including updating AGENTS.md when they find a new development or debugging technique, updating REQUIREMENTS.md when requirements are implemented, new bugs are found or new features are identified and updating DESIGN.md when soemthing from the design is updated.  
