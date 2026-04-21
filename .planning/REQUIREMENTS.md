# Requirements: pickaladder

## Core Value
A robust and professional platform for pickleball ladder management that prioritizes ranking integrity and seamless external integrations.

## v1 Scope

### 1. Code Quality & Audit (AUDIT)
- **AUDIT-01**: Perform a comprehensive code review of the entire project to identify technical debt, security vulnerabilities, and architectural inconsistencies.
- **AUDIT-02**: Standardize project configuration using a centralized configuration file (replacing environment variable reliance where appropriate).
- **AUDIT-03**: Audit Firestore data models and access patterns for efficiency and cost-optimization.

### 2. Ranking & Leaderboard (RANK)
- **RANK-01**: Transition leaderboard sorting from "Average Score" to an "ELO-First" or "Glicko-2" ranking system to better reflect player skill.
- **RANK-02**: Implement "Shootout" (Court Movement) logic for session-based group play.
- **RANK-03**: Implement "Inactivity Decay" or "Activity Requirements" to prevent rank protection by top players.

### 3. DUPR Integration (DUPR)
- **DUPR-01**: Implement DUPR API synchronization to allow users to pull and display their official DUPR ratings.
- **DUPR-02**: Add a "Verified Match" status for matches where all participants have linked DUPR accounts.

### 4. Quality & Infrastructure (QUAL)
- **QUAL-01**: Implement static type checking project-wide using `mypy`.
- **QUAL-02**: Expand the test suite to include integration tests for the match processing service and leaderboard logic.
- **QUAL-03**: Establish an automated CI/CD pipeline for linting, type checking, and test execution.

### 5. Session-First Workflow & Batch Recording (BATCH)
- **BATCH-01**: Users can create a "Session" by selecting a pool of 4-8 players.
- **BATCH-02**: Users can record matches sequentially using a UI pre-populated with players from the session pool.
- **BATCH-03**: Users can use "Winner-First" scoring shortcuts (2-tap) for rapid data entry.
- **BATCH-04**: Users have access to a mobile-optimized "Quick Log" view for court-side use.
- **BATCH-05**: Participants can batch-verify all matches within a session in a single action.

### 6. Vocabulary Transition (VOCAB)
- **VOCAB-01**: Update all landing page and welcome text (index, welcome, login templates) to use "Groups" or "Tournaments" instead of "Ladders".
- **VOCAB-02**: Refactor UI messages and constants (constants/messages.py) to use contextual terms.
- **VOCAB-03**: Rename internal code symbols where 'ladder' is used as a functional descriptor (excluding 'pickaladder' branding and infrastructure).
- **VOCAB-04**: Update project documentation (REQUIREMENTS.md, README.md, etc) to reflect the new terminology.

### 7. Match Display Standardization (DISPLAY)
- **DISPLAY-01**: Define standardized win/loss CSS classes in `data-displays.css` using the High Contrast (Volt/Black) palette.
- **DISPLAY-02**: Refactor `match_list_item.html` to use the new standardized classes.
- **DISPLAY-03**: Update match summary page to ensure full visual alignment.
- **DISPLAY-04**: Standardize score typography globally using the 'Oswald' font.
- **DISPLAY-05**: Update recent matches component to match the new design.

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUDIT-01 | Phase 1 | Completed |
| AUDIT-02 | Phase 1 | Completed |
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
| BATCH-03 | Phase 4 | Pending |
| BATCH-04 | Phase 4 | Pending |
| BATCH-05 | Phase 4 | Pending |
| VOCAB-01 | Phase 5 | Complete |
| VOCAB-02 | Phase 5 | Complete |
| VOCAB-03 | Phase 5 | Complete |
| VOCAB-04 | Phase 5 | Complete |
| DISPLAY-01 | Phase 6 | Complete |
| DISPLAY-02 | Phase 6 | Complete |
| DISPLAY-03 | Phase 6 | Complete |
| DISPLAY-04 | Phase 6 | Complete |
| DISPLAY-05 | Phase 6 | Complete |
