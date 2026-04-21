# Phase 6: Match Display Standardization - Research

**Researched:** 2025-03-24
**Domain:** UI/UX, CSS Standardization, High Contrast Theme
**Confidence:** HIGH

## Summary

This phase focuses on standardizing the match display UI across the application using a High Contrast (Volt/Black) theme. The current implementation uses inconsistent badge classes (`badge-success`, `badge-danger`, `badge-volt`) and varying typography for match scores. We will introduce standardized classes `.status-win` and `.status-loss` in `data-displays.css` and enforce the use of the `Oswald` font for all score displays to align with the "Court & Volt" design system.

**Primary recommendation:** Define `.status-win` (Volt background, Dark text) and `.status-loss` (Dark background, Light/Volt text) as the source of truth for match results and apply `var(--font-score)` to all score elements.

## User Constraints (from CONTEXT.md)

*No CONTEXT.md found for this phase. Research is based on Phase 6 objectives and requirements.*

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DISPLAY-01 | Define standardized win/loss CSS classes in data-displays.css. | Identified `data-displays.css` as the target for new classes `.status-win` and `.status-loss`. |
| DISPLAY-02 | Update match_list_item.html. | Analyzed current badge usage in `match_list_item.html` (success/danger). |
| DISPLAY-03 | Update match summary page (summary.html). | Verified `.score-display` usage and font integration in `summary.html`. |
| DISPLAY-04 | Standardize score typography (Oswald font). | Confirmed `Oswald` is imported in `layout.html` and available via `var(--font-score)`. |
| DISPLAY-05 | Update recent matches component (_recent_matches.html). | Identified existing `score-badge-win/loss` in `_recent_matches.html` for refactoring. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Bootstrap | 4.5.3 | Base UI Framework | Project standard |
| Oswald Font | (Google Fonts) | Score Typography | Part of brand identity |
| Inter Font | (Google Fonts) | Primary UI Font | Project standard |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|--------------|
| Font Awesome | 6.5.1 | Iconography | Standard for UI icons |

**Installation:**
No new packages required. Changes are CSS and Template based.

## Architecture Patterns

### Recommended Project Structure
```
pickaladder/
├── static/
│   └── css/
│       ├── data-displays.css  # [New standardized classes here]
│       └── variables.css     # [Volt and Font variables]
└── templates/
    ├── components/
    │   ├── match_list_item.html
    │   └── _recent_matches.html
    └── match/
        └── summary.html
```

### Pattern 1: High Contrast Badges
**What:** Using `.status-win` and `.status-loss` to provide high-visibility feedback on match outcomes.
**When to use:** Match lists, summary cards, and recent match feeds.
**Example:**
```css
/* Source: Proposed for data-displays.css */
.status-win {
    background-color: var(--color-volt) !important;
    color: var(--text-on-accent) !important;
    font-weight: var(--fw-bold);
    text-transform: uppercase;
}

.status-loss {
    background-color: var(--text-primary) !important;
    color: var(--bg-secondary) !important;
    font-weight: var(--fw-bold);
    text-transform: uppercase;
    border: 1px solid var(--border-color);
}
```

### Anti-Patterns to Avoid
- **Inline Styling for Result Colors:** Avoid using `style="color: green"` or Bootstrap generic `badge-success` for match outcomes. Use the semantic `.status-win` class.
- **Hand-rolling Font Families:** Always use `var(--font-score)` for scores instead of hardcoding `font-family: 'Oswald'`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Color Management | Hardcoded HEX codes | CSS Variables | Centralized theme control in `variables.css` |
| Font Loading | Custom @font-face | Google Fonts in `layout.html` | Performance and caching |

## Common Pitfalls

### Pitfall 1: CSS Specificity
**What goes wrong:** Existing Bootstrap classes or styles in `style.css` (like `.badge-success`) might override the new `.status-win` classes.
**How to avoid:** Use `!important` in `data-displays.css` for the standardized status classes or remove conflicting classes from templates.

### Pitfall 2: Dark Mode Contrast
**What goes wrong:** "Black" text on "Volt" might look different in Dark Mode if variables are changed.
**How to avoid:** Verify contrast in both Light and Dark modes. `var(--text-on-accent)` is specifically designed to work with the Volt color.

## Code Examples

### Standardized Score Typography
```html
<!-- Proposed for match_list_item.html and _recent_matches.html -->
<span class="font-score fs-large">{{ user_score }} - {{ opp_score }}</span>
```

### High Contrast Result Badge
```html
<!-- Standardized badge structure -->
<span class="badge status-win rounded-circle w-28 h-28 d-inline-flex align-items-center justify-content-center">W</span>
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `badge-success` / `badge-danger` | `.status-win` / `.status-loss` | Phase 6 | Consistent High Contrast brand look |
| Mixed Fonts | Enforced `Oswald` for scores | Phase 6 | Professional, specialized typography |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | "Black" in Volt/Black means `var(--text-primary)` | Summary | Theme might feel "off" if it should be pure #000 |

## Open Questions

1. **Pure Black vs. Dark Navy:** Should the "Black" in the theme be the current dark navy `#111827` (text-primary) or a pure `#000000`?
   - Recommendation: Stick with `#111827` (var(--text-primary)) for consistency with the current design system.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Flask App | ✓ | 3.13.11 | — |
| Node.js | Development | ✓ | 24.11.0 | — |
| Oswald Font | Typography | ✓ | Google Fonts | — |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest |
| Config file | mypy.ini / pyproject.toml |
| Quick run command | `pytest tests/test_match.py` |
| Full suite command | `pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DISPLAY-01 | Standardized CSS exists | Smoke | `ls pickaladder/static/css/data-displays.css` | ✅ |
| DISPLAY-02 | Match list uses status classes | UI/Reg | `grep "status-win" pickaladder/templates/components/match_list_item.html` | ❌ Wave 0 |

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | Ensure match data displayed is escaped (Jinja2 default) |

### Known Threat Patterns for CSS/UI

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| XSS via Match Data | Tampering | Jinja2 auto-escaping (default active) |

## Sources

### Primary (HIGH confidence)
- `pickaladder/static/css/variables.css` - Verified color and font variables.
- `pickaladder/templates/layout.html` - Confirmed font imports.
- `pickaladder/static/css/data-displays.css` - Target for standardization.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Core fonts and framework identified.
- Architecture: HIGH - Templates and CSS locations confirmed.
- Pitfalls: MEDIUM - Specificity issues are predictable but need care.

**Research date:** 2025-03-24
**Valid until:** 2025-04-24
