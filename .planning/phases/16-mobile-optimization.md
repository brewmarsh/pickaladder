# Phase 16: Mobile-First Optimization & PWA

**Goal:** Ensure a premium, app-like experience for players recording matches courtside, even with poor connectivity.

## Objectives
1. **PWA Foundation:** Implement full Manifest and Service Worker support for "Add to Home Screen".
2. **Mobile UX Audit:** Refine all critical workflows (Match Recording, Tournament Viewing) for thumb-friendly interaction.
3. **Offline Resilience:** Implement basic caching strategies to prevent data loss during transient disconnects.
4. **Performance:** Optimize asset delivery and rendering for slower mobile networks.

## Implementation Plan

### 1. PWA Implementation
- Create `manifest.json` with app icons and theme colors.
- Implement a basic `sw.js` (Service Worker) for asset caching.
- Add PWA install prompt logic.

### 2. Mobile UI Refinement
- Redesign the Match Recording form for maximum mobile efficiency.
- Implement "Sticky" navigation headers for mobile views.
- Ensure all tables are horizontally scrollable or card-based on small screens.

### 3. Verification
- Use Playwright to simulate mobile device environments.
- Verify manifest and service worker registration in production-like environments.

## Success Criteria
1. Lighthouse "PWA" score > 90.
2. "Record Match" flow completed in under 3 taps from the dashboard on mobile.
3. App remains functional for viewing recent activity without an active internet connection.
