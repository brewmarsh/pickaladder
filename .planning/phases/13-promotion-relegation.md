# Phase 13: Promotion & Relegation Logic

**Goal:** Automate the process of moving players/teams between divisions at the end of a season based on performance.

## Objectives
1. Define **Promotion/Relegation Rules** (e.g., Top 2 move up, Bottom 2 move down).
2. Implement a **Season Finalization Workflow** that captures standings and triggers movements.
3. Build a **Transition Preview UI** for group admins to review movements before applying them.
4. Support **Historical Record Keeping** of division memberships across seasons.

## Implementation Plan

### 1. Business Logic
- Create `MovementService` to calculate transitions between Division A and Division B.
- Implement logic to handle edge cases (e.g., top/bottom divisions).

### 2. Season State Management
- Add a "Finalizing" status to Seasons.
- Store "Final Standings" snapshot to ensure historical accuracy even if players leave the group.

### 3. UI Components
- Add a "Finalize Season" button to the Management Hub.
- Create a modal/page showing "Players moving UP" and "Players moving DOWN".

## Success Criteria
1. Season can be closed, preventing further match recording.
2. Participant lists for the *next* season are automatically suggested based on movements.
3. Movements correctly follow defined numerical thresholds (e.g., Top X, Bottom Y).
