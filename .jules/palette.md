## 2026-06-28 - Adding ARIA labels to icon-only buttons
**Learning:** Many icon-only action links (like the settings gear or team rename pencil) were lacking `aria-label` attributes. The emojis act as visual cues for sighted users but do not provide context to screen readers, violating WCAG principles for interactive elements.
**Action:** When adding or auditing floating action buttons (FABs) or icon-only inline actions, always ensure a descriptive `aria-label` or screen-reader-only text is present to indicate the action's purpose.
