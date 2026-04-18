# External Integrations

**Analysis Date:** 2025-02-14

## APIs & External Services

**Sports Analytics:**
- DUPR API - Fetching and synchronizing pickleball player ratings
  - SDK/Client: `requests` (implemented in `pickaladder/user/services/dupr_service.py`)
  - Auth: `DUPR_API_KEY` (env var)

**Image Services:**
- DiceBear - Dynamic avatar generation for users without profile pictures
  - Implementation: Template filters in `pickaladder/__init__.py` and `pickaladder/user/services/core.py`
  - Auth: Public API (no key required)
- Imgur (Legacy) - Previously used for image hosting, dependency remains but active code uses Firebase Storage
  - SDK: `imgur-python` 0.2.4

**Email:**
- Flask-Mail - Outgoing emails for notifications, invitations, and verifications
  - Implementation: `pickaladder/extensions.py`, initialized in `pickaladder/__init__.py`
  - Auth: `MAIL_USERNAME`, `MAIL_PASSWORD` (env vars)

## Data Storage

**Databases:**
- Firebase Firestore - Primary NoSQL database for users, groups, matches, and tournaments
  - Connection: `GOOGLE_APPLICATION_CREDENTIALS` or `FIREBASE_CREDENTIALS_JSON`
  - Client: `firebase-admin` SDK

**File Storage:**
- Firebase Storage - Profile pictures and other user-uploaded media
  - Service: Firebase Cloud Storage (`pickaladder.firebasestorage.app`)
  - Client: `firebase-admin` storage module (`pickaladder/user/services/profile.py`)

**Caching:**
- None detected (Server-side sessions handled via `Flask-Login` and cookies)

## Authentication & Identity

**Auth Provider:**
- Firebase Auth - User authentication (Sign up, Sign in, Password resets)
  - Implementation: Integrated via `firebase-admin` and `Flask-Login` (`pickaladder/auth/routes.py`)
  - Auth tokens: Verified using `firebase_admin.auth.verify_id_token`

## Monitoring & Observability

**Error Tracking:**
- None detected (Standard logging used in `pickaladder/config.py` and service modules)

**Logs:**
- Standard output/error captured by Docker and Gunicorn. Detailed mail logging in `pickaladder/__init__.py`.

## CI/CD & Deployment

**Hosting:**
- Self-hosted or VPS running Docker Compose. Nginx as the entry point with SSL.

**CI Pipeline:**
- GitHub Actions - Automates testing, linting, and deployment (`.github/workflows/`)
  - Workflows: `ci.yaml` (testing), `beta.yml` (beta deployment), `deploy.yml` (production deployment), `agent-readiness.yaml` (quality check)

## Environment Configuration

**Required env vars:**
- `SECRET_KEY` - Flask session security
- `FIREBASE_PROJECT_ID` - Firebase identification
- `FIREBASE_API_KEY` - Client-side Firebase operations
- `MAIL_USERNAME` / `MAIL_PASSWORD` - Email delivery
- `DUPR_API_KEY` - Pickleball rating synchronization

**Secrets location:**
- `.env` file (local development)
- GitHub Actions Secrets (CI/CD)
- `serviceAccountKey.json` / `firebase_credentials.json` (Firebase Auth)

## Webhooks & Callbacks

**Incoming:**
- None detected (Application primarily uses polling or user-initiated actions)

**Outgoing:**
- None detected

---

*Integration audit: 2025-02-14*
