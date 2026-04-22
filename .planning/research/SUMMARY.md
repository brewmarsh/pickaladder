# Research Summary: Group and Team Management Refactor

**Domain:** Sports/Pickleball Ladder Application
**Researched:** 2026-04-21
**Overall confidence:** HIGH

## Executive Summary

The current implementation of Groups and Teams in `pickaladder` follows a "Static Pairing" model where a Team is strictly defined as a unique combination of exactly two players. This model is efficient for tracking head-to-head stats for specific pairs but lacks the flexibility needed for sports clubs or "Named Teams" with rosters.

Architecturally, the project suffers from inconsistencies in data schema (camelCase vs snake_case for timestamps) and a blurred line between service and repository layers. `GroupService` and `TeamService` handle everything from low-level Firestore updates to complex business logic and UI enrichment.

The research recommends moving towards a **Hybrid Team Model** that supports both ephemeral auto-pairings (for individual stat tracking) and managed "Named Teams" (with rosters). This will reduce UX friction during match recording and allow for richer social features.

## Key Findings

**Stack:** Flask (Python) with Firebase Firestore/Storage. Current implementation relies on `firebase-admin`.
**Architecture:** Moving from Procedural Services to a Repository/Service pattern.
**Critical pitfall:** Inconsistent timestamp fields (`createdAt` vs `created_at`) and divergent stat calculation sources (cached vs real-time).

## Implications for Roadmap

Suggested phase structure for the refactor:

1. **Phase 1: Foundation & Standardization** - Resolve schema inconsistencies and consolidate duplicate team creation logic.
   - Addresses: `createdAt`/`created_at` split, Duplicate `create_team` logic.
2. **Phase 2: Repository Layer Extraction** - Decouple data access from business logic.
   - Addresses: Service bloat and architectural inconsistency.
3. **Phase 3: Dynamic Teams & Rosters** - Implement the `memberships` junction collection and allow teams to have more than 2 members.
   - Addresses: "Dynamic Teams" requirement.
4. **Phase 4: UX Integration** - Update match recording and team management UIs to leverage the new flexible model.
   - Addresses: Friction in naming and team selection.

**Phase ordering rationale:**
Standardization and Layering (Phases 1 & 2) are prerequisites for building the more complex Dynamic Team features (Phases 3 & 4) without adding more technical debt.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Standard Flask/Firestore patterns. |
| Features | HIGH | Well-understood sports app requirements. |
| Architecture | MEDIUM | Proposed pattern is standard but requires significant refactor of existing services. |
| Pitfalls | HIGH | Common issues in early-stage Firestore projects. |

## Gaps to Address

- **Performance impact of dynamic aggregation**: Calculating ELO and stats for flexible rosters might require denormalization or Cloud Functions which were not fully explored in this research.
- **Backwards Compatibility**: Migration strategy for existing "Static" teams into the new "Named" or "Pairing" categories needs detailed mapping.
