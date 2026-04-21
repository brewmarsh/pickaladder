# Phase 5: Vocabulary Transition - Research

**Researched:** 2026-04-21
**Domain:** UI/UX Terminology Transition
**Confidence:** HIGH

## Summary
The research focused on identifying all occurrences of "ladder(s)" and "Ladder(s)" to be transitioned to "group(s)" or "tournament(s)" while strictly preserving "pickaladder" branding and Firebase infrastructure strings. The transition is primarily a UI and documentation task, as the core logic and database schema already use "group" and "tournament" terminology.

## User Constraints
- Preserve `pickaladder` branding in text and URLs.
- Preserve Firebase infrastructure strings (Project ID, Auth Domain, Storage Buckets).
- Map "Ladder" to "Group" or "Tournament" based on context.

## File Edit Map

### 1. Templates
- **`pickaladder/templates/index.html`**: Update "manage your pickleball ladders" -> "manage your pickleball groups and tournaments".
- **`pickaladder/templates/welcome.html`**: Update "platform for pickleball ladders and tournaments" -> "platform for pickleball groups and tournaments".
- **`pickaladder/templates/login.html`**: Update "Run Ladders" -> "Manage Groups".
- **`pickaladder/templates/community.html`**: Update "It's like a ladder for pickleball" -> "It's like a tournament for pickleball".
- **`pickaladder/templates/friends/index.html`**: Update "It's like a ladder for pickleball" -> "It's like a tournament for pickleball".

### 2. Documentation & Metadata
- **`README.md`**: Update header and feature descriptions.
- **`docs/REQUIREMENTS.md`**: Update "Multiple Ladder Rankings" -> "Multiple Group/Tournament Rankings".
- **`pyproject.toml`**: Update description to "A pickleball group and tournament management application".
- **`docs/DESIGN.md`**: Update conceptual overview.

## Conclusion
The objective is to remove "ladder" as a concept and replace it with "groups" or "tournaments". We will **not** rename the package `pickaladder` or infrastructure strings.
