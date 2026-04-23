# Research: Tournament & Season Management

**Target Milestone:** Milestone 6 (v1.2)
**Research Date:** 2026-04-23

## Objective
Expand the competitive capabilities of `pickaladder` by supporting advanced tournament formats and recurring league seasons.

## Current State Audit
- **Format Support:** Only Round Robin (`generator.py`).
- **Structure:** Tournaments are standalone entities.
- **Participation:** Basic invite/accept flow implemented.
- **Reporting:** Basic match history tracking.

## Expansion Areas

### 1. Tournament Formats
- **Single Elimination:** Classic bracket style. Requires power-of-2 participant handling (or byes).
- **Double Elimination:** Winners and Losers brackets. Higher complexity for pairing logic.
- **Swiss System:** Non-eliminating format where players with similar records play each other. Ideal for medium-sized groups without the time for full Round Robin.

### 2. Season/League Management
- **Recurring Play:** Group owners should be able to define "Seasons" (e.g., Spring 2026).
- **Promotion/Relegation:** Automatically move players between "Divisions" or "Courts" based on season-end standings.
- **Season Trophies:** Bragging rights/badges for season winners.

### 3. Tournament Visualization
- **Brackets:** Dynamic SVG or CSS-based bracket view.
- **Standings:** Rich table with sets won/lost, point differentials, and tie-break logic.

## Technical Considerations
- **Pairing Engine:** Needs to be flexible to support multiple generators.
- **Byes Handling:** Logic for odd numbers of participants.
- **Seedings:** Using ELO/DUPR ratings to seed brackets fairly.

## Recommendations for Phase Breakdown
1. **Phase 10: Elimination Brackets** (Brackets, Byes, Seedings).
2. **Phase 11: Season Infrastructure** (recurring entities, standing aggregation).
3. **Phase 12: Advanced Standings & Tie-breaks** (Point differential, H2H).

## Sources
- USAP (USA Pickleball) Tournament guidelines.
- Wikipedia: Tournament pairing systems.
