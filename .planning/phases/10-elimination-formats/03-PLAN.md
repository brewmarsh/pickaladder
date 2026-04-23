# Plan: 10-03: Bracket Progression Logic

**Goal:** Automate match advancement in tournament brackets upon match completion.

## Tasks
1. [ ] Implement `TournamentService.handle_match_completion(match_id, winner_uid)`.
2. [ ] Add "Winner Advancement" logic:
    - Identify the next match in the bracket (Round N+1).
    - Populate the correct player slot (Player 1 or Player 2) based on the current match's `bracketPosition`.
3. [ ] Add "Loser Drop" logic for Double Elimination:
    - Identify the corresponding match in the Losers Bracket.
    - Populate the correct player slot.
4. [ ] Integrate with the global `MatchService` to trigger tournament updates automatically.
5. [ ] Add unit tests in `tests/test_tournament_progression.py`.

## Technical Details
- **Positioning:** For a match at `bracketPosition` $P$ in Round $R$, the winner moves to `bracketPosition` $floor(P/2)$ in Round $R+1$.
- **Slot Selection:** If $P$ is even, the winner becomes Player 1 in the next match. If $P$ is odd, Player 2.
- **Double Elimination Drops:** This follows a specific mapping (e.g., Losers of Winners R1 go to Losers R1).

## Success Criteria
- [ ] Recording a score for a tournament match automatically creates or updates the next match in the bracket.
- [ ] In Double Elimination, the loser is correctly placed in the Losers bracket.
- [ ] The visual bracket reflects these updates in real-time.
