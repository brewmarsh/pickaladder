### **Best Practices Repository Template (Final Version)**

This guide provides a comprehensive template for structuring a new repository, incorporating containerization, workflow automation, CI/CD, and developer experience best practices.

---

### **1. Core Components & Directory Structure**

A clean directory structure is the foundation. This structure separates source code, tests, and configuration, and includes a dedicated folder for GitHub Actions workflows.

```
/
├── .github/                # GitHub-specific files
│   └── workflows/          # CI/CD workflows
│       └── ci.yml
├── my_app/                 # Your Python package source code
│   ├── __init__.py
│   └── ...
├── tests/                  # All tests for your application
│   ├── __init__.py
│   └── helpers.py
│   └── ...
├── .gitignore              # Specifies intentionally untracked files to ignore
├── AGENTS.md               # Instructions for AI agents working on the repo
├── Dockerfile              # Instructions to build a production-ready container
├── docker-compose.yml      # Defines the development environment
├── Makefile                # Simplifies and standardizes common commands
├── README.md               # The front door to your project for humans
├── requirements.txt        # Production dependencies
└── requirements-dev.txt    # Development and testing tools
```

---

### **2. `README.md` and Project Badging**

The `README.md` is the most important file for human developers. It should be clear, concise, and provide all the necessary information to get started.

#### **`README.md` Template**

```markdown
# My Awesome Project

<!-- Add your project badges here -->
[![CI Status](https://github.com/YOUR_USERNAME/YOUR_REPO/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/YOUR_REPO/actions)
[![codecov](https://codecov.io/gh/YOUR_USERNAME/YOUR_REPO/branch/main/graph/badge.svg?token=YOUR_CODECOV_TOKEN)](https://codecov.io/gh/YOUR_USERNAME/YOUR_REPO)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A brief description of what this project is and what it does.

## Features

- Feature 1
- Feature 2
- ...

## Getting Started

### Prerequisites

- Docker
- Docker Compose
- `make`

### Installation & Setup

1.  **Clone the repository:**
    ```sh
    git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
    cd YOUR_REPO
    ```
2.  **Build and start the application containers:**
    ```sh
    make up
    ```
3.  The application will be available at `http://localhost:5000`.

## Running Tests

To run the full suite of tests and code quality checks:
```sh
make all-checks
```

## Contributing
<!-- Optional: Add guidelines for how others can contribute to your project. -->
```

#### **Adding Badges**

Badges provide a quick visual indicator of your project's health.

*   **CI Status:** This shows the status of your CI pipeline. The URL needs to be updated with your GitHub username and repository name.
*   **Code Coverage:** Services like [Codecov](https://about.codecov.io/) or [Coveralls](https://coveralls.io/) can be integrated with your CI pipeline to provide a coverage badge. You'll need to sign up for one of these services and add a repository token to your GitHub secrets.
*   **License and Code Style:** These are static badges that show the project's license and declare the use of `ruff` for formatting.

---

### **3. Dependency Management & Containerization**

#### **Dependency Management**
Separating production dependencies from development tools is a best practice.

**`requirements.txt` (Production Dependencies)**
```
# --- Application Dependencies ---
Flask==3.1.2
gunicorn==23.0.0
# ... add other application-specific libraries here
```

**`requirements-dev.txt` (Development Tools)**
```
# --- Development & Code Quality Tools ---
# Include production dependencies
-r requirements.txt

# Add development-specific tools
ruff==0.13.0
bandit==1.8.6
mypy==1.18.1
coverage==7.3.2
testtools==2.5.0
```
When setting up a local development environment, you would install this file: `pip install -r requirements-dev.txt`.

#### **Containerization**

**`Dockerfile` (Production-Ready)**
This `Dockerfile` uses a multi-stage build to create a smaller, more secure final image.

```dockerfile
# Stage 1: Build Stage - Install all dependencies (including dev)
FROM python:3.9-bullseye AS builder
WORKDIR /app
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

# Stage 2: Final Stage - Copy only what's needed for production
FROM python:3.9-slim-bullseye
WORKDIR /app

# Copy only the installed production packages from the builder stage
COPY --from=builder /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
# Copy the application code
COPY . .

# Replace 'my_app:create_app()' with the actual entrypoint of your app.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "my_app:create_app()"]
```

**`docker-compose.yml` (Development Environment)**
This file is for *development* and uses a volume to mount your code for live-reloading.

```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - .:/app
    depends_on:
      - db
    environment:
      - FLASK_ENV=development

  db:
    image: postgres:13
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
      POSTGRES_DB: app_db
    volumes:
      - postgres_data:/var/lib/postgresql/data/

volumes:
  postgres_data:
```

---

### **4. Workflow Automation**

#### **`Makefile` (Standardized Commands)**
The `Makefile` is the entrypoint for all common tasks. This version includes a `clean` command and an `install` command for local setup.

```makefile
.PHONY: up build test coverage lint format security type-check all-checks clean install

install:
	pip install --upgrade pip
	pip install -r requirements-dev.txt

up:
	docker compose up -d

build:
	docker compose build --no-cache

clean:
	docker compose down -v --remove-orphans
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -r {} +

test:
	docker compose exec web python -m unittest discover tests

coverage:
	docker compose exec web coverage run -m unittest discover tests
	docker compose exec web coverage report -m

lint:
	ruff check --fix .

format:
	ruff format .

security:
	docker compose exec web bandit -r .

type-check:
	docker compose exec web mypy .

# This target now runs the checks inside the container for consistency with CI
all-checks:
	docker compose exec web ruff check .
	docker compose exec web bandit -r .
	docker compose exec web mypy .
	docker compose exec web coverage run -m unittest discover tests
```

#### **`AGENTS.md` (AI Agent Instructions)**
This file guides AI agents, ensuring they follow project standards.

```markdown
# Agent Instructions

## 1. High-Level Architectural Overview
<!-- Describe the application's architecture. What framework is it? What are the key components? -->

## 2. Key Files and Directories
- `README.md`: Project overview, setup, and usage.
- `my_app/`: Main application source code.
- `tests/`: All application tests.
- `Makefile`: All common commands for development and CI.

## 3. Build, Test, and Deployment
- **To set up the local environment:** `make install`
- **To build and start the application:** `make up`
- **To run all tests and quality checks:** `make all-checks`
- **To clean the environment:** `make clean`

<!-- Add any other important commands or troubleshooting tips. -->

## 4. Coding Standards and Contribution Guidelines
<!-- Specify any coding style (e.g., PEP 8), commit message format, etc. -->
```

---

### **5. Continuous Integration (CI) with GitHub Actions**

A CI pipeline automatically runs your tests and checks. This more efficient workflow runs the checks directly in the CI environment, avoiding the overhead of Docker-in-Docker.

Create the file `.github/workflows/ci.yml`:

```yaml
name: CI Pipeline

on: [push, pull_request]

jobs:
  build-and-test:
    runs-on: ubuntu-latest

    steps:
      - name: Check out code
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'

      - name: Install dependencies
        run: |
          pip install --upgrade pip
          pip install -r requirements-dev.txt

      - name: Run linter
        run: ruff check .

      - name: Run formatter check
        run: ruff format --check .

      - name: Run security scan
        run: bandit -r .

      - name: Run type checking
        run: mypy .

      - name: Run tests with coverage
        run: coverage run -m unittest discover tests

      - name: Generate coverage report
        run: coverage xml # Generate XML for Codecov

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
          token: ${{ secrets.CODECOV_TOKEN }} # Required for private repos
```
