# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.10.0] - 2026-02-23

### Added
- Beta environment infrastructure.
- Nightly database sync (Prod -> Beta).
- "Copy to Clipboard" for share cards.
- App subdomain standardization.

### Fixed
- User menu z-index and hover target issues.
- Profile photo fetching in Group leaderboard cards.
- Firebase Storage bucket initialization.
- Group match redirect logic.

### Changed
- Incremented version to v0.10.0.
- Updated Nginx routing to `app.pickaladder.com`.

### Security
- SEO safeguards (noindex) for the Beta environment.

### Refactored
- Massive system-wide ACL reduction (Cognitive Load refactoring) across Auth, Group, Tournament, and Match domains.
