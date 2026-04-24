# Plan: 12-02: Tie-break Reason UI

**Goal:** Provide transparency to users by showing why someone is ranked higher in a tie (H2H, PD, etc.).

## Tasks
1. [ ] Update `StandingAggregator._resolve_ties` to attach a `tie_break_reason` to each player in a tied group.
2. [ ] Update `pickaladder/templates/season/view.html` to display the `tie_break_reason` (e.g., as a badge or subscript).
3. [ ] Update `tests/test_standing_aggregator.py` to verify the presence and correctness of the reason.

## Technical Details
- **Reason Mapping:**
    - Level 1: "H2H"
    - Level 2: "PD"
    - Level 3: "H2H PD"
    - Level 4: "PF"
- **Implementation:** When `_resolve_ties` successfully splits a group, it should tag the resulting players with the level that caused the split.

## Success Criteria
- [ ] Users can see "H2H" or "PD" next to names in the standings table when a tie-breaker was applied.
- [ ] Logic correctly identifies the *first* level that successfully differentiated the players.
