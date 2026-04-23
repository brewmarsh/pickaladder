# Plan: 10-02: Double Elimination & Visualization

**Goal:** Implement Double Elimination logic and frontend bracket visualization.

## Tasks
1. [ ] Research and implement `generate_double_elimination` in `TournamentGenerator`.
2. [ ] Update `publish_bracket` to support `DOUBLE_ELIMINATION`.
3. [ ] Create `pickaladder/templates/tournaments/_bracket.html` for rendering brackets.
4. [ ] Implement CSS for bracket lines and responsive layout.

## Technical Details
- **Double Elimination:** 
  - Winners Bracket: Same as Single Elimination.
  - Losers Bracket: Losers from each round of the Winners bracket drop down to play each other.
  - Final: Winner of Winners vs Winner of Losers.
- **Visualization:** Use CSS Flexbox with `::before/::after` pseudo-elements or SVG paths to draw bracket connections.

## Success Criteria
- [ ] Correct pairing generation for both brackets.
- [ ] Users can see a visual map of the tournament flow.
- [ ] Winners drop to the correct slots in the Losers bracket.
