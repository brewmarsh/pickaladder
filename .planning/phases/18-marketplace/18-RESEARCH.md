# Phase 18: Division & Group Marketplace - Research

**Researched:** 2026-04-24
**Domain:** Group Discovery & Membership Orchestration
**Confidence:** HIGH

## Summary
The current system supports "Public" and "Private" groups via an `is_public` boolean. Public groups are discoverable in the "Community Hub" and allow immediate joining, while private groups are invite-only. There is no middle-ground "Request to Join" system or visibility controls for Divisions (which are currently nested within Seasons). Phase 18 will unify these into a dedicated Marketplace with a "Featured" discovery layer and formal membership request workflows.

## Standard Stack

| Library | Version | Purpose |
|---------|---------|---------|
| Bootstrap | 5.3.2 | UI Framework |
| Firestore | Native | Data storage for groups, requests, and divisions |
| Flask-WTF | ~1.2 | Form handling for Join Requests |

## Architecture Patterns

### 1. Group Visibility & Privacy
- **Groups:** Currently have `is_public: bool`.
- **Divisions:** Currently `TypedDict` within `Season`. They lack independent visibility fields.
- **Recommendation:** Add `visibility` (enum: PUBLIC, UNLISTED, PRIVATE) and `join_policy` (enum: OPEN, REQUEST, INVITE) to both `Group` and `Division`.

### 2. Membership Requests (The "Missing Link")
- **Current State:** No "Join Request" system exists. Only `group_invites` (outgoing).
- **Pattern:** Create a `membership_requests` collection.
  - `groupId` / `divisionId` (ref)
  - `userId` (ref)
  - `status` (PENDING, APPROVED, DECLINED)
  - `message` (string)

### 3. Discovery UI (Volt Theme)
- **Primary Color:** Electric Lime (`#84CC16`) is the "Volt" accent.
- **Carousel:** Use Bootstrap 5.3 native `carousel` component for "Featured" groups.
- **Filtering:** Current search is in-memory for the first 20 users/10 groups. 
- **Recommendation:** Implement Firestore-side filtering for the marketplace to support scale.

## Common Pitfalls

- **Firestore Array Limits:** Members are stored in an array. This caps at 1MB/document (~several thousand members). The marketplace should account for "Large Groups" by checking if we need a sub-collection for members.
- **Division Orphanage:** Divisions are currently tied to Seasons. If a user joins a Division from the marketplace, they must be correctly added to the parent Group and the specific Season participants list.

## Validation Architecture
- **Framework**: Pytest.
- **Test Strategy**: Mock Firestore for repository tests; use Playwright for UI flow verification.
