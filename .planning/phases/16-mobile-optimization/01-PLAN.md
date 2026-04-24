# Plan: 16-01: PWA Manifest & App-Like Foundation

**Goal:** Lay the groundwork for PWA support and implement the initial mobile-first visual refinements.

## Tasks
1. [x] Generate app icons (192x192, 512x512) and place in `static/img/pwa/`.
2. [x] Create `pickaladder/static/manifest.json`.
3. [x] Register the Manifest in `pickaladder/templates/layout.html`.
4. [x] Implement `pickaladder/static/service-worker.js` with basic static asset caching (V1).
5. [x] Update `pickaladder/main/routes.py` to serve the service worker with the correct MIME type.
6. [x] Add `apple-touch-icon` and `theme-color` meta tags.

## Technical Details
- **Theme Color:** #111827 (Black-Navy)
- **Background Color:** #111827
- **Caching Strategy:** Stale-while-revalidate for CSS/JS; Network-first for dynamic API routes.

## Success Criteria
- [x] Browser's "Add to Home Screen" prompt is triggered on mobile devices.
- [x] Application has a dedicated splash screen and icon when launched from the home screen.
- [x] Service worker successfully installs and activates.
