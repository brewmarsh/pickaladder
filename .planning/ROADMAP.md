# Roadmap: pickaladder

## Phases

- [x] **Phase 1: Quality Foundation & Audit** - Comprehensive code review and establishing quality gates.
- [x] **Phase 2: Ranking Logic & Integrity** - Transitioning to skill-based ranking and automated movement.
- [x] **Phase 3: External Integration & Advanced Ranking** - DUPR sync and rank health management.
- [x] **Phase 4: Session-First Workflow & Batch Recording** - Streamlining courtside match logging via session pools.
- [x] **Phase 5: Vocabulary Transition** - Transitioning terminology from "Ladders" to "Groups" and "Tournaments".
- [x] **Phase 6: Match Display Standardization** - Standardizing win/loss indicators and typography.
- [x] **Phase 7: Group & Team Foundation Refactor** - Standardizing architecture and data models for groups and teams.
- [x] **Phase 8: Dynamic Team Model** - Enabling flexible team structures beyond simple pairings.
- [x] **Phase 9: Group/Team UX Modernization** - Improving management workflows and visibility for teams and groups.
- [x] **Phase 10: Elimination Formats** - Advanced tournament logic (Single/Double Elimination) and bracket visualization.
- [x] **Phase 11: Season Infrastructure** - Generalizing tournament entities into recurring seasons and standings.
- [ ] **Phase 12: Advanced Standings & Tie-breaks** - Implementing H2H logic, set-based standings, and point-differential rules.

---

## Phase Details

### Phase 12: Advanced Standings & Tie-breaks
**Goal**: Implement robust, tournament-standard standing aggregation with complex tie-break rules.
**Depends on**: Phase 11
**Success Criteria**:
  1. Rankings correctly reflect H2H results when match wins are equal.
  2. Three-way ties are resolved via Point Differential or Reset Rule.
  3. Standings dashboard displays all data points used in the hierarchy.
**Plans**:
- [x] 01-PLAN.md — Standing Aggregator Core.
- [ ] 02-PLAN.md — Tie-break Reason UI.

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Quality Foundation & Audit | 2/2 | Completed | 2026-04-17 |
| 2. Ranking Logic & Integrity | 1/1 | Completed | 2026-04-17 |
| 3. External Integration & Advanced Ranking | 1/1 | Completed | 2026-04-17 |
| 4. Session-First Workflow & Batch Recording | 3/3 | Completed | 2026-04-21 |
| 5. Vocabulary Transition | 1/1 | Completed | 2026-04-21 |
| 6. Match Display Standardization | 1/1 | Completed | 2026-04-21 |
| 7. Group & Team Foundation Refactor | 3/3 | Completed | 2026-04-21 |
| 8. Dynamic Team Model | 3/3 | Completed | 2026-04-22 |
| 9. Group/Team UX Modernization | 3/3 | Completed | 2026-04-22 |
| 10. Elimination Formats | 4/4 | Completed | 2026-04-23 |
| 11. Season Infrastructure | 2/2 | Completed | 2026-04-23 |
| 12. Advanced Standings | 1/2 | In Progress | - |
