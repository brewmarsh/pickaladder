# Technology Stack

**Project:** pickaladder
**Researched:** 2026-04-21

## Recommended Stack

### Core Framework
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | 3.11+ | Backend logic | Current project standard, strong typing support. |
| Flask | 3.x | Web Framework | Lightweight, easy to route for various blueprints. |

### Database
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Google Cloud Firestore | Native | Data Persistence | NoSQL scalability, real-time potential, good integration with Firebase Auth. |

### Infrastructure
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Firebase Admin SDK | 6.x | Backend Integration | High-privileged access to Firestore and Storage. |
| Firebase Storage | Native | Media Hosting | Group and user profile pictures. |

### Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Pydantic | 2.x | Data Validation | For strong typing of "MatchSubmission" and "Team" models before Firestore write. |
| WTForms | Latest | Form handling | Standardizing input validation for groups and matches. |

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Database | Firestore | PostgreSQL | Firestore is already deeply integrated; a move to SQL would require a total rewrite. |
| Pattern | Repository | Active Record | Firestore doesn't have a native ORM that supports Active Record well in Python. |

## Installation

```bash
# Core
pip install firebase-admin flask pydantic wtforms

# Dev dependencies
pip install pytest black mypy ruff
```

## Sources
- Official Firebase Python SDK Docs
- Current `requirements.txt` analysis
