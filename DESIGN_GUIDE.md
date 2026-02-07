
Pickaladder Brand Guidelines
Version 1.0 | Theme: "Court & Volt"
1. The Philosophy
Pickleball is fast, social, and electric. Our design reflects this.
 * "Volt" (Electric Lime): Represents the energy of the game, the ball itself, and the dopamine hit of winning. It is used sparingly for high-value actions.
 * "Court" (Royal Blue): Represents the playing surface, structure, and community trust. It is used for navigation and layout.
2. Color Palette
Primary Colors
 * Electric Volt (Accent/Action): #84CC16 (Light Mode) / #BEF264 (Dark Mode)
   * Usage: Primary CTA buttons ("Record Match"), "Winner" badges, Rank indicators.
 * Court Royal (Structure/Nav): #2563EB (Light Mode) / #3B82F6 (Dark Mode)
   * Usage: Navigation bars, active tabs, links, headers.
Neutral Colors (The "Arena")
 * Day Mode Background: #F3F4F6 (Cool Gray 100) - Reduces glare compared to pure white.
 * Night Mode Background: #0F172A (Slate 900) - Adds depth compared to pure black.
 * Card Surface (Day): #FFFFFF (White)
 * Card Surface (Night): #1E293B (Slate 800)
Functional Colors
 * Success (Win): #10B981 (Emerald) - Use for secondary positive actions.
 * Danger (Loss/Delete): #EF4444 (Red) - Use for errors or "Loss" streaks.
 * Warning (Pending): #F59E0B (Amber) - Use for "Pending Request" states.
3. Typography Selection
To match the "Court & Volt" theme, we need fonts that are highly legible (for stats/scores) but athletic.
Primary Font (Headings & UI): Inter
 * Why: It is the gold standard for modern UI. It’s clean, scans fast on mobile, and has a "technical" feel that fits a stats app.
 * Weights: Bold (700) for Headers, Medium (500) for Buttons.
Secondary Font (Numbers & Scores): Oswald
 * Why: A condensed, tall sans-serif that mimics a stadium scoreboard.
 * Usage: Use only for the Scoreboard (e.g., 11 - 9), Player Ranks (#1), and Win Probability percentages (65%).
Implementation (CSS)
/* Add to style.css */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700&family=Oswald:wght@500;700&display=swap');

:root {
    --font-ui: 'Inter', sans-serif;
    --font-score: 'Oswald', sans-serif;
}

body { font-family: var(--font-ui); }
.score-display, .rank-badge { font-family: var(--font-score); letter-spacing: 1px; }

4. UI Component Library
A. Buttons
 * The "Volt" Button (Primary CTA)
   * Style: Background Electric Volt, Text Dark Navy (#111827).
   * Shape: Rounded-pill (border-radius: 50rem) or slightly rounded (.rounded-lg).
   * Effect: Subdued shadow on hover to make it "pop" or "glow."
 * The "Court" Button (Secondary)
   * Style: Background Court Royal, Text White.
   * Usage: "Add Friend", "View Details", Navigation.
B. Badges & Status
 * Winner Badge: Pill shape, Volt background, Dark Navy text. Do not use white text on Volt.
 * Streak Badge: Small circle or rounded square next to the user avatar.
   * Win Streak: Green text/border.
   * Loss Streak: Red text/border.
C. Cards
 * Day Mode: White background, thin border (#E5E7EB), soft shadow (shadow-sm).
 * Night Mode: Slate 800 background, thin border (#334155), no shadow (shadows are invisible on dark backgrounds).
5. Accessibility & Contrast Rules
 * Rule 1: Never put White text on Electric Volt. It fails accessibility standards. Always use Dark Navy or Black text on Volt backgrounds.
 * Rule 2: Ensure "Court Royal" Blue is not too dark on the Dark Mode background. Use the lighter #3B82F6 variant for Dark Mode visibility.