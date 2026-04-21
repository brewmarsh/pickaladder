# Research: Match Display Inconsistencies

## Current State
- **Global Match Lists:** Use Bootstrap-style `badge-success` (Green) for wins and `badge-danger` (Red) for losses.
- **Match Summary Page:** Uses a custom "Volt/Black" theme with `winner-glow`, `winner-crown`, and `border-volt`.
- **Quick Log:** Uses the High Contrast (Volt/Black) theme.
- **Colors:**
    - Win: Green (`--success-color: #10B981`)
    - Loss: Red (`--danger-color: #EF4444`)
    - Volt: Electric Lime (`--accent-color: #84CC16`)

## Proposed Standardization (High Contrast Volt/Black)
- **Win Indicator:** Use Volt background with dark text.
- **Loss Indicator:** Use a dark/slate background with light text (subtle).
- **Typography:** Standardize score displays using the `Oswald` font family (`--font-score`).
- **Cards:** Standardize match card layout and borders.

## Target Files
- `pickaladder/static/css/data-displays.css`: Define new `.status-win` and `.status-loss` classes.
- `pickaladder/templates/components/match_list_item.html`: Update badges to use new classes.
- `pickaladder/templates/match/summary.html`: Ensure consistency with the new classes.
- `pickaladder/templates/components/_recent_matches.html`: Update recent matches display.
