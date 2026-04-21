# Research: Batch Match Recording Workflows

**Domain:** Sports Session Management (Pickleball, Tennis, Padel)
**Researched:** 2024-10-24
**Confidence:** HIGH

## Executive Summary

Recording sequential sports matches (especially in pickleball) is often a high-friction task that leads to data abandonment. Users typically play 3–6 games in a session with a fixed pool of 4–8 players. Current "standard" flows (like DUPR) require a full search-and-select process for every single game, which is too slow for courtside use.

A seamless **Batch Recording Workflow** must shift the focus from "Match" to "Session." By pre-selecting a pool of players at the start, the app can reduce the data entry for subsequent games to just **two taps + score entry**.

---

## 1. Core Workflow: The "Session-First" Pattern

Instead of recording matches in isolation, the UI should be built around a "Session" container.

### Phase A: Setup (Once per session)
1. **Define the Pool:** Select 4–12 players who are present at the court.
2. **Contextual Defaults:** Select game format (e.g., "Single game to 11") and location.

### Phase B: The "Next Game" Loop (Repeat for each game)
1. **Select Players from Pool:** Display the 8 players as large avatars. Tapping an avatar assigns them to a team (Side A or Side B). 
   - *Optimization:* Use "Drag to Court" or "Tap to Side" mechanics.
2. **Enter Score:** 
   - *The "Winner-First" Shortcut:* Tap the winning team first (auto-sets their score to 11). Then enter the loser's score.
   - *The "Stepper" Method:* Use large +/- buttons for live scoring (if recording during play).
3. **Quick Submit:** A single "Save & Next" button that archives the game and resets the "Court" for the next selection while keeping the "Pool" visible.

---

## 2. UI Patterns for Sequential Recording

### 2.1 The "Pool & Court" Layout
- **Top Section (The Court):** Two slots for Team A, two for Team B. 
- **Middle Section (The Pool):** A grid of avatars for the 4-8 players in the session.
- **Bottom Section (Recent Games):** A horizontal "filmstrip" of recently recorded scores in this session for quick verification.

### 2.2 Interactive Rotations (Smart Suggestions)
For groups of 5, 6, or 8, the app can automate the "Who's Next?" question:
- **Round Robin Engine:** Automatically populates the 4 players for the next game based on a rotation schedule (ensures everyone plays with everyone).
- **"Sit Out" Tracking:** Visually flag players who haven't played in the last 2 games.

### 2.3 Fast-Entry Score Patterns
| Pattern | Description | Best For |
|---------|-------------|----------|
| **Preset Grid** | A grid of numbers (0-15). Tap one for Team A, one for Team B. | Post-game logging. |
| **Winner Toggle** | A toggle for "Team A won" + a single numeric input for Team B's score. | Standard games (to 11). |
| **Live Stepper** | Large + / - buttons on the left and right sides of the screen. | Courtside live scoring. |

---

## 3. Minimizing Repetitive Data Entry

To make it "seamless," apply these rules:
1. **Sticky Rosters:** The last-used session pool should be the default "Quick Select" for the next day.
2. **Bulk Entry Mode:** Allow users to log 3+ games at once at the *end* of a session. 
   - *UI Pattern:* A vertical list of empty "Match Cards." You fill the players for Match 1, and Match 2 *pre-fills* with a different combination of the same players.
3. **Auto-Partnering:** If 4 players are selected, the app should remember the most common pairings for that group or suggest the "fairest" split based on ratings.

---

## 4. Technical Feasibility & Constraints

### Feasibility: HIGH
- **State Management:** Requires a robust local state (e.g., Redux or specialized Hook) to manage the "Session" and "Draft Matches" before final submission.
- **Offline Support:** Essential. Users often have poor connectivity at sports complexes. The app must allow full session recording offline and sync once back on Wi-Fi.

### Blockers / Risks
- **Player Verification:** If results count for a rating (like DUPR), "Batch Recording" by one person needs a way for others to "Bulk Approve." 
- **Ghost Players:** If a session includes a guest not in the app, the UI must allow "Ghost" placeholders that can be linked to real accounts later.

---

## 5. MVP Recommendation

**Phase 1: The "Manual Session"**
- A screen to pick a pool of 6 players.
- A "Match Creator" that uses those 6 players as the only options.
- A "Post-Game" entry form: "Who won? [Side A/Side B] Score: [11] - [X]".

**Phase 2: The "Smart Session"**
- Automatic Round Robin rotation suggestions.
- Voice-to-Score (optional).
- Session Summary (Total wins/losses for the day).

## Sources
- **DUPR App Workflow:** Multi-step, high friction (individual match focus).
- **Pickleball Brackets:** Tournament focus, strong validation but complex.
- **Best Practices for Sports UI:** "3-tap rule," large touch targets (44px), high contrast for outdoor use.
