# Roadmap: pickaladder

## Phases

- [x] **Phase 1: Quality Foundation & Audit**
- [x] **Phase 2: Ranking Logic & Integrity**
- [x] **Phase 3: External Integration & Advanced Ranking**
- [x] **Phase 4: Session-First Workflow & Batch Recording**
- [x] **Phase 5: Vocabulary Transition**
- [x] **Phase 6: Match Display Standardization**
- [x] **Phase 7: Group & Team Foundation Refactor**
- [x] **Phase 8: Dynamic Team Model**
- [x] **Phase 9: Group/Team UX Modernization**
- [x] **Phase 10: Elimination Formats**
- [x] **Phase 11: Season Infrastructure**
- [x] **Phase 12: Advanced Standings & Tie-breaks**
- [x] **Phase 13: Promotion & Relegation Logic**
- [x] **Phase 14: Seasonal Analytics & Reporting**
- [x] **Phase 15: Social Engagement & Feed**
- [x] **Phase 16: Mobile-First Optimization & PWA**
- [x] **Phase 17: Community Messaging & Real-time Chat**
- [x] **Phase 18: Division & Group Marketplace**
- [x] **Phase 19: Competitive Challenges & Wagering**
- [x] **Phase 20: Visual Polish & UX Refinement**
- [x] **Phase 21: Data Access & Scale**
- [ ] **Phase 22: Architectural Refactor & Type Safety**
- [ ] **Phase 23: Production Readiness & Observability**

---

## Phase Details

... (existing phases) ...

### Phase 21: Data Access & Scale
**Goal**: Address performance bottlenecks and implement reusable pagination.
**Depends on**: Phase 20
**Requirements**: [SCALE-01, SCALE-02, SCALE-03]
**Success Criteria**:
  1. Standardized pagination utility for Firestore.
  2. N+1 queries resolved in core views.
**Plans**:
- [x] 21-01-PLAN.md — Pagination & Query Optimization

### Phase 22: Architectural Refactor & Type Safety
**Goal**: Modularize the codebase and achieve 100% type hint coverage.
**Depends on**: Phase 21
**Requirements**: [ARCH-01, ARCH-02]
**Success Criteria**:
  1. Large route files split into modules.
  2. Zero ANN violations in ruff.
**Plans**:
- [x] 22-01-PLAN.md — Modularize User Routes & Service Consolidation
- [ ] 22-02-PLAN.md — Modularize Group Routes & Service Consolidation
- [ ] 22-03-PLAN.md — Type Safety Blitz

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
...
| 20. Visual Polish & UX Refinement | 2/2 | Completed | 2026-04-27 |
| 21. Data Access & Scale | 1/1 | Completed | 2026-04-27 |
| 22. Architectural Refactor | 1/3 | In Progress|  |
| 23. Production Readiness | 0/1 | Planned | - |
