# Technology Stack

**Analysis Date:** 2025-02-14

## Languages

**Primary:**
- Python 3.11 - Backend logic, Flask application, CLI scripts, tests

**Secondary:**
- JavaScript (Vanilla) - Client-side interactive logic, service workers for PWA (`pickaladder/static/js/main.js`)
- HTML5/CSS3 - User interface templates (Jinja2) and styling (`pickaladder/templates/`, `pickaladder/static/css/`)

## Runtime

**Environment:**
- Python 3.11-bullseye (via Docker)
- Gunicorn 25.1.0 - WSGI HTTP Server
- Nginx - Reverse proxy and static file server

**Package Manager:**
- uv - Primary dependency management and lockfile (`uv.lock`)
- pip - Used in `Dockerfile` for installation from `requirements.txt`
- Lockfile: `uv.lock` present

## Frameworks

**Core:**
- Flask 3.1.3 - Primary web framework (`pickaladder/__init__.py`)
- Flask-Login 0.6.3 - User session management
- Flask-WTF 1.2.2 - Form handling and CSRF protection

**Testing:**
- Pytest 9.0.2 - Test runner (`tests/`)
- Pytest-Flask 1.3.0 - Flask application testing integration
- Playwright 0.7.2 - End-to-end testing (`tests/e2e/`)
- Coverage 7.13.4 - Test coverage reporting

**Build/Dev:**
- Ruff 0.15.4 - Linting and formatting
- Bandit 1.9.4 - Security linting
- Mypy 1.19.1 - Static type checking
- MkDocs 1.6.1 - Documentation generation (`mkdocs.yml`)

## Key Dependencies

**Critical:**
- `firebase-admin` 7.2.0 - Firebase integration for database, auth, and storage
- `pydantic` 2.12.5 - Data validation and settings management
- `Pillow` 12.1.1 - Image processing for profile pictures

**Infrastructure:**
- `gunicorn` 25.1.0 - Production WSGI server
- `werkzeug` - WSGI utility library (ProxyFix, Secure Filenames)

## Configuration

**Environment:**
- Configured via environment variables and `.env` files.
- `pickaladder/config.py` - Centralized configuration management.
- Key configs: `FLASK_ENV`, `SECRET_KEY`, `FIREBASE_API_KEY`, `FIREBASE_PROJECT_ID`, `MAIL_SERVER`, `DUPR_API_KEY`.

**Build:**
- `pyproject.toml` - Project metadata and tool configurations.
- `Dockerfile` - Container build specification.
- `docker-compose.yml` - Multi-container orchestration (web, nginx).
- `mypy.ini` - Mypy specific configuration.

## Platform Requirements

**Development:**
- Docker and Docker Compose
- Python 3.11+
- uv (recommended)

**Production:**
- Linux (Debian-based recommended for Docker bullseye)
- Docker Engine & Docker Compose
- Nginx for SSL termination (Let's Encrypt support via `init-letsencrypt.sh`)

---

*Stack analysis: 2025-02-14*
