# Phase 10: Advanced Tournament Formats (Elimination)

**Goal:** Implement Single and Double Elimination tournament formats with bracket visualization.

## Objectives
1. Implement **Single Elimination** pairing generator.
2. Implement **Double Elimination** pairing generator.
3. Add **Bracket Visualization** (SVG/CSS) to the tournament view.
4. Support **Seeding** based on ELO/DUPR ratings.

## Implementation Plan

### 1. Seeding & Byes
- Enhance `TournamentGenerator` to sort participants by rating.
- Implement Bye-logic for non-power-of-2 participant counts.

### 2. Elimination Logic
- **Single Elimination:** Create a recursive or iterative generator for $N$ rounds.
- **Double Elimination:** Implement a "Losers bracket" that receives losers from the primary bracket.

### 3. Frontend Visualization
- Create a `tournaments/_bracket.html` partial.
- Use a flexbox-based CSS layout to render brackets responsively.

## Success Criteria
1. User can select "Single Elimination" or "Double Elimination" when creating a tournament.
2. The system correctly generates match pairings for all rounds (including byes).
3. Tournament view displays a visual bracket connecting matches.
4. Ratings correctly influence initial match seeding.
