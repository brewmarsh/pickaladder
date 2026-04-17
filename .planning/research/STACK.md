# Technology Stack

**Project:** pickaladder
**Researched:** 2025-05-24

## Recommended Stack

### Core Framework
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | 3.12+ | Backend Logic | Robust handling of ranking algorithms and data processing. |
| Flask | 3.0+ | Web Framework | Lightweight and flexible for the existing codebase. |

### Database
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Firestore | Native | Data Storage | Document-based structure is ideal for flexible group/match data. |

### Infrastructure
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Docker | Latest | Containerization | Consistency across dev/prod environments. |
| Nginx | Latest | Reverse Proxy | Security and SSL termination. |

### Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `firebase-admin` | Latest | DB Access | Primary interaction with Firestore. |
| `duprly` (Unofficial) | GitHub | DUPR Integration | Community-driven wrapper for DUPR API exploration. |
| `scipy` / `numpy` | Latest | Advanced Ranking | Only if implementing complex Glicko-2 or proprietary rating systems. |

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Database | Firestore | PostgreSQL | Firestore is already deeply integrated; transition would be high-effort for low immediate gain. |
| Rating API | DUPR | Pickleball.com | DUPR is the broader industry standard for amateur and pro play. |

## Installation

```bash
# Core Dependencies
pip install flask firebase-admin python-dotenv

# Dev Dependencies
pip install pytest ruff mypy
```

## Sources

- [DUPR API Documentation](https://api.dupr.gg/swagger-ui/index.html)
- [Project Codebase Audit](CODEBASE_AUDIT.md)
