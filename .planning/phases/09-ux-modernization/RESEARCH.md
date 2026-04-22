# Phase 09: Group/Team UX Modernization - Research

**Researched:** 2026-04-22
**Domain:** Frontend UI/UX, Sports Management Hubs, Multi-step Wizards
**Confidence:** HIGH

## Summary

This phase focuses on consolidating and modernizing the user experience for managing Groups and Teams. The primary goals are to create a unified "Management Hub" for group owners, a multi-step "Team Creation Wizard," and high-contrast dashboard widgets that align with the "Volt/Black" design system established in Phase 6.

**Primary recommendation:** Use Bootstrap 4 Tabs for the Management Hub to provide a clean, single-page feel for administrators, and a jQuery-driven multi-step form for the Team Wizard to reduce cognitive load during complex team formation.

<user_constraints>
## User Constraints (from CONTEXT.md)

*Note: No 09-CONTEXT.md was found; assuming discretion within the scope of requirements.*

### Locked Decisions
- Consolidate group management into a 'Management Hub'.
- Implement a multi-step 'Team Creation Wizard'.
- Use High-Contrast (Volt/Black) theme for team ranking widgets.

### the agent's Discretion
- Template names and specific route structures.
- UI library usage (Bootstrap 4 + jQuery preferred based on codebase audit).
- Dashboard widget placement within the existing Competition Hub.

### Deferred Ideas (OUT OF SCOPE)
- Real-time chat within the Management Hub.
- Advanced statistical modeling for teams (keeping to standard ranking/record).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TEAMUX-01 | Unified 'Management Hub' for group owners. | Use Bootstrap 4 Tabs to consolidate Roster, Invites, and Settings [CITED: layout.html, Bootstrap docs]. |
| TEAMUX-02 | Simplified team creation wizard. | Multi-step form (Identity -> Roster -> Confirm) reduces friction for dynamic team formation [CITED: Best Practices search]. |
| TEAMUX-03 | High-contrast dashboard widgets for team rankings. | Leverage existing `--color-volt` and `Oswald` font for high-energy display [VERIFIED: data-displays.css, layout.html]. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Bootstrap | 4.5.3 | Grid & Components | Project's base UI framework [VERIFIED: layout.html]. |
| jQuery | 3.5.1 | DOM manipulation | Base for Bootstrap and custom interactive logic [VERIFIED: layout.html]. |
| Flask-WTF | ~1.0 | Form handling | Standard for CSRF and validation in this app [VERIFIED: routes.py]. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|--------------|
| FontAwesome | 6.x | Icons | Used for dashboard icons and hub navigation [VERIFIED: layout.html]. |
| Google Fonts | Oswald | Typography | Standardized for high-energy sports stats [VERIFIED: layout.html]. |

**Installation:**
No new packages required. Existing infrastructure covers all needs.

## Architecture Patterns

### Recommended Project Structure
```
pickaladder/
├── group/
│   └── routes.py         # New route: /manage/<group_id>
├── teams/
│   └── routes.py         # New route: /wizard
└── templates/
    ├── components/
    │   └── _team_ranking_widget.html  # High-contrast widget
    ├── group/
    │   └── management_hub.html         # Consolidated admin hub
    └── team/
        └── wizard.html                 # Multi-step creation flow
```

### Pattern 1: Bootstrap 4 Tabs for Management Hub
**What:** Use the Nav-Tabs component to switch between management contexts (Roster, Invites, Settings) without full page reloads.
**When to use:** Consolidating disparate admin actions like promoting members, deleting invites, and updating group info.

### Pattern 2: Multi-Step "Progressive Disclosure" Wizard
**What:** Hide/Show sections of a single form using jQuery to guide the user through team creation.
**Steps:**
1. **Step 1 (Identity):** Name and optional metadata.
2. **Step 2 (Roster):** Member selection (using a searchable list).
3. **Step 3 (Review):** Summary of choices before final POST.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tab Switching | Custom JS toggle logic | Bootstrap Tabs | Handles ARIA roles and state management out of the box. |
| Progress Bars | Custom CSS animations | Bootstrap Progress | Consistent styling and easier width control. |
| Searchable Selects | Complex auto-complete | Filterable list with jQuery | Lower complexity than adding a new library like Select2. |

## Common Pitfalls

### Pitfall 1: Permission Leaks
**What goes wrong:** Regular members accessing the Management Hub via direct URL.
**Why it happens:** Route protection only checks for login, not group role.
**How to avoid:** Use `GroupService.is_group_admin` check at the start of the hub route.

### Pitfall 2: Mobile Roster Selection
**What goes wrong:** Large groups making the roster selection step a "scroll of death" on mobile.
**Why it happens:** Listing 50+ members as checkboxes.
**How to avoid:** Implement a simple text filter that hides/shows member rows based on search input.

## Code Examples

### Wizard Step Transition (jQuery)
```javascript
// Source: Community patterns for Bootstrap 4 wizards
$('.next-step').click(function() {
    const nextStep = $(this).data('next');
    $('.wizard-step').hide();
    $(`#step-${nextStep}`).show();
    $('.progress-bar').css('width', (nextStep * 33) + '%');
});
```

### High-Contrast Widget Pattern
```html
<!-- Proposed components/_team_ranking_widget.html -->
<div class="card bg-dark text-white border-volt">
    <div class="card-body p-3">
        <div class="d-flex justify-content-between align-items-center">
            <h5 class="text-volt oswald mb-0">TEAM NAME</h5>
            <span class="badge badge-volt">RANK #1</span>
        </div>
        <div class="mt-2 fs-large oswald">12 - 4 (75%)</div>
        <div class="trend-sparkline mt-1">...</div>
    </div>
</div>
```

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Scattered admin buttons | Unified Management Hub | Improved admin efficiency and clearer mental model. |
| Single long forms | Multi-step Wizard | Higher completion rates for complex entities (Teams). |
| Standard card styles | Volt/Black High Contrast | Stronger brand identity and better visibility for top performers. |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Bootstrap 4 is sufficient for the Hub | Summary | Might need more modern Flexbox control; though standard in current project. |
| A2 | Users prefer Wizard over single form | Architecture | Some power users might find steps slower; however, multi-step is better for roster selection. |

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Bootstrap | Hub/Wizard | ✓ | 4.5.3 | — |
| jQuery | Wizard logic | ✓ | 3.5.1 | — |
| Oswald Font | High Contrast UI | ✓ | — | Inter/Sans-serif |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Pytest |
| Config file | `mypy.ini` (for types), `pytest.ini` (implied) |
| Quick run command | `pytest tests/test_group.py tests/test_team_service.py` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TEAMUX-01 | Access control for Hub | integration | `pytest tests/test_group.py` | ✅ (Existing) |
| TEAMUX-02 | Team creation logic | unit | `pytest tests/test_team_service.py` | ✅ (Existing) |
| TEAMUX-03 | Template rendering | smoke | `pytest tests/test_app.py` | ✅ (Existing) |

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V4 Access Control | yes | `is_group_admin(group, user_id)` logic |
| V5 Input Validation | yes | WTForms validation in `forms.py` |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Insecure Direct Object Ref (IDOR) | Information Disclosure | Verify group ownership before rendering Hub. |
| Cross-Site Request Forgery (CSRF) | Tampering | Use `csrf_token()` in all Hub/Wizard forms. |

## Sources

### Primary (HIGH confidence)
- `pickaladder/templates/layout.html` - Verified Bootstrap/jQuery/Font versions.
- `pickaladder/group/routes.py` - Verified existing management routes.
- `pickaladder/static/css/data-displays.css` - Verified Volt/Black CSS patterns.

### Secondary (MEDIUM confidence)
- Google Search: Best practices for sports management apps (Vertex AI Grounding).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Verified in layout.html.
- Architecture: HIGH - Fits project patterns.
- Pitfalls: MEDIUM - Based on general UX experience.

**Research date:** 2026-04-22
**Valid until:** 2026-05-22
