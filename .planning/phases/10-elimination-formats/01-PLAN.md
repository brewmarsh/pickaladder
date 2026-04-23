# Plan: 10-01: Single Elimination Core

**Goal:** Implement the backend logic for generating Single Elimination tournament brackets.

## Tasks
1. [ ] Update `TournamentGenerator` in `pickaladder/tournament/services/generator.py` to support `generate_single_elimination`.
2. [ ] Implement `_calculate_rounds` to determine required rounds and byes based on participant count.
3. [ ] Add seeding logic using `glicko2` or `elo` stats from the user profiles.
4. [ ] Create unit tests in `tests/test_tournament_generator.py` to verify bracket integrity.

## Technical Details
- **Byes:** If $N$ is not a power of 2, the top $(2^k - N)$ seeds get a bye in the first round.
- **Pairings:** Classic high-seed vs low-seed pairing ($1$ vs $N$, $2$ vs $N-1$, etc.).

## Testing Strategy
- Verify $N=4$ (perfect power of 2, no byes).
- Verify $N=5$ (3 byes, 1 match in round 1).
- Verify seeding: Highest rated player is at index 0.
