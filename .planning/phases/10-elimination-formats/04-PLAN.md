# Plan: 10-04: Double Elimination Logic (Losers & Finals)

**Goal:** Implement the complex movement logic for Double Elimination losers and the Grand Finals reset.

## Tasks
1. [ ] Define the mapping for "Winners Bracket Loser" to "Losers Bracket Slot".
2. [ ] Implement `TournamentProgression._drop_loser` in `pickaladder/tournament/services/progression.py`.
3. [ ] Implement "Grand Finals" logic:
    - Winner of Winners vs Winner of Losers.
    - If the Losers Bracket winner wins the first match, trigger a "Bracket Reset" (2nd match).
4. [ ] Update `publish_bracket` to pre-generate initial Losers Bracket matches for Double Elimination.
5. [ ] Add unit tests in `tests/test_double_elimination.py`.

## Technical Details
- **Loser Mapping:** 
    - Losers from Winners Round 1 drop to Losers Round 1.
    - Losers from Winners Round 2 drop to Losers Round 2.
    - Mapping is typically cross-bracket to avoid immediate rematches.
- **Grand Finals:** Match with `bracketType: "FINALS"`. Special logic for `match_count: 2`.

## Success Criteria
- [ ] Losers from the Winners bracket automatically populate the next available slot in the Losers bracket.
- [ ] The Grand Finals correctly identifies if a rematch is needed.
- [ ] All 100% passing tests for DE flow.
