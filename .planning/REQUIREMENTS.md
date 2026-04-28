# Requirements: pickaladder

## Core Value
A robust and professional platform for pickleball ladder management that prioritizes ranking integrity and seamless external integrations.

## v1 Scope

### 1. Code Quality & Audit (AUDIT)
- **AUDIT-01**: Perform a comprehensive code review of the entire project to identify technical debt, security vulnerabilities, and architectural inconsistencies. [DONE]
- **AUDIT-02**: Standardize project configuration using a centralized configuration file. [DONE]
- **AUDIT-03**: Audit Firestore data models and access patterns for efficiency and cost-optimization. [DONE]

### 2. Ranking & Leaderboard (RANK)
- **RANK-01**: Transition leaderboard sorting to an "ELO-First" or "Glicko-2" ranking system. [DONE]
- **RANK-02**: Implement "Shootout" (Court Movement) logic for session-based group play. [DONE]
- **RANK-03**: Implement "Inactivity Decay" or "Activity Requirements" to prevent rank protection. [DONE]

### 3. DUPR Integration (DUPR)
- **DUPR-01**: Implement DUPR API synchronization to allow users to pull and display official ratings. [DONE]
- **DUPR-02**: Add a "Verified Match" status for matches with DUPR-linked participants. [DONE]

### 4. Quality & Infrastructure (QUAL)
- **QUAL-01**: Implement static type checking project-wide using `mypy`. [DONE]
- **QUAL-02**: Expand the test suite to include integration tests for match processing and leaderboard logic. [DONE]
- **QUAL-03**: Establish an automated CI/CD pipeline for linting, type checking, and test execution. [DONE]

### 5. Session-First Workflow & Batch Recording (BATCH)
- **BATCH-01**: Users can create a "Session" by selecting a pool of 4-8 players. [DONE]
- **BATCH-02**: Users can record matches sequentially using a pre-populated UI. [DONE]
- **BATCH-03**: Users can use "Winner-First" scoring shortcuts (2-tap) for rapid data entry. [DONE]
- **BATCH-04**: Users have access to a mobile-optimized "Quick Log" view for court-side use. [DONE]
- **BATCH-05**: Participants can batch-verify all matches within a session in a single action. [DONE]

### 6. Vocabulary Transition (VOCAB)
- **VOCAB-01**: Update all landing page and welcome text to use "Groups" or "Tournaments". [DONE]
- **VOCAB-02**: Refactor UI messages and constants to use contextual terms. [DONE]
- **VOCAB-03**: Rename internal code symbols where 'ladder' is used as a functional descriptor. [DONE]
- **VOCAB-04**: Update project documentation to reflect the new terminology. [DONE]

### 7. Match Display Standardization (DISPLAY)
- **DISPLAY-01**: Define standardized win/loss CSS classes in `data-displays.css`. [DONE]
- **DISPLAY-02**: Refactor match list items to use new standardized classes. [DONE]
- **DISPLAY-03**: Update match summary page for full visual alignment. [DONE]
- **DISPLAY-04**: Standardize score typography globally using the 'Oswald' font. [DONE]
- **DISPLAY-05**: Update recent matches component to match the new design. [DONE]

### 12. Division & Group Marketplace (MARKET)
- **MARKET-01**: Implement a centralized marketplace for discovering public groups and divisions with search and filtering. [DONE]
- **MARKET-02**: Implement a membership request workflow allowing users to apply to join restricted groups. [DONE]
- **MARKET-03**: Enable group owners to manage visibility (Public/Unlisted/Private) and join policies (Open/Request/Invite). [DONE]

### 13. Competitive Challenges & Wagering (CHAL)
- **CHAL-01**: Implement a formal challenge lifecycle (Issue, Accept, Decline, Expire) with persistent state. [DONE]
- **CHAL-02**: Implement a virtual economy (Social Credits) with atomic wagering transactions and escrow logic. [DONE]
- **CHAL-03**: Integrate challenges with match recording for automated wager resolution based on match outcome. [DONE]
### 14. Visual Polish & UX Refinement (POLISH)
- **POLISH-01**: Refine global CSS variables and remove legacy bridging code for a unified "Pro" aesthetic. [DONE]
- **POLISH-02**: Standardize component styling (Cards, Buttons, Modals) across all features (Messaging, Marketplace, Challenges). [DONE]
- **POLISH-03**: Optimize mobile navigation and touch targets for better usability on small devices. [DONE]
- **POLISH-04**: Address page-specific UX "papercuts" (alignment, spacing, typography) in Dashboard and Community views. [DONE]

### 15. Performance, Scale & Integrity (SCALE/ARCH)
- **SCALE-01**: Standardized pagination utility for Firestore to handle large collections (Users, Matches, Groups). [DONE]
- **SCALE-02**: N+1 query resolution in high-traffic views (Leaderboards, Group Hub) using batching or denormalization. [DONE]
- **ARCH-01**: Modularize monolithic route files (user/routes, group/routes) into smaller, domain-specific sub-blueprints. [DONE]
- **ARCH-02**: Achieve 100% Type Hint coverage and resolve all ANN violations in Ruff. [DONE]

### 16. Production Readiness & Observability (PROD)
- **PROD-01**: Implement a centralized, structured logging system for error tracking and system health monitoring. [DONE]
- **PROD-02**: Implement a persistent administrative audit trail in Firestore to track sensitive actions. [DONE]

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
...
| POLISH-03 | Phase 20 | Completed |
| POLISH-04 | Phase 20 | Completed |
| SCALE-01 | Phase 21 | Completed |
| SCALE-02 | Phase 21 | Completed |
| ARCH-01 | Phase 22 | Completed |
| ARCH-02 | Phase 22 | Completed |
| PROD-01 | Phase 23 | Completed |
| PROD-02 | Phase 23 | Completed |

| AUDIT-03 | Phase 1 | Completed |
| QUAL-01 | Phase 1 | Completed |
| QUAL-03 | Phase 1 | Completed |
| RANK-01 | Phase 2 | Completed |
| RANK-02 | Phase 2 | Completed |
| QUAL-02 | Phase 2 | Completed |
| RANK-03 | Phase 3 | Completed |
| DUPR-01 | Phase 3 | Completed |
| DUPR-02 | Phase 3 | Completed |
| BATCH-01 | Phase 4 | Completed |
| BATCH-02 | Phase 4 | Completed |
| BATCH-03 | Phase 4 | Completed |
| BATCH-04 | Phase 4 | Completed |
| BATCH-05 | Phase 4 | Completed |
| VOCAB-01 | Phase 5 | Completed |
| VOCAB-02 | Phase 5 | Completed |
| VOCAB-03 | Phase 5 | Completed |
| VOCAB-04 | Phase 5 | Completed |
| DISPLAY-01 | Phase 6 | Completed |
| DISPLAY-02 | Phase 6 | Completed |
| DISPLAY-03 | Phase 6 | Completed |
| DISPLAY-04 | Phase 6 | Completed |
| DISPLAY-05 | Phase 6 | Completed |
| REFACTOR-01 | Phase 7 | Completed |
| REFACTOR-02 | Phase 7 | Completed |
| REFACTOR-03 | Phase 7 | Completed |
| DYNAMIC-01 | Phase 8 | Completed |
| DYNAMIC-02 | Phase 8 | Completed |
| DYNAMIC-03 | Phase 8 | Completed |
| TEAMUX-01 | Phase 9 | Completed |
| TEAMUX-02 | Phase 9 | Completed |
| TEAMUX-03 | Phase 9 | Completed |
| COMM-01 | Phase 17 | Completed |
| COMM-02 | Phase 17 | Completed |
| COMM-03 | Phase 17 | Completed |
| MARKET-01 | Phase 18 | Completed |
| MARKET-02 | Phase 18 | Completed |
| MARKET-03 | Phase 18 | Completed |
| CHAL-01 | Phase 19 | Completed |
| CHAL-02 | Phase 19 | Completed |
| CHAL-03 | Phase 19 | Completed |
| POLISH-01 | Phase 20 | Completed |
| POLISH-02 | Phase 20 | Completed |
| POLISH-03 | Phase 20 | Completed |
| POLISH-04 | Phase 20 | Completed |
