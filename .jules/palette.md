## 2026-06-28 - Adding ARIA labels to icon-only buttons
**Learning:** Many icon-only action links (like the settings gear or team rename pencil) were lacking `aria-label` attributes. The emojis act as visual cues for sighted users but do not provide context to screen readers, violating WCAG principles for interactive elements.
**Action:** When adding or auditing floating action buttons (FABs) or icon-only inline actions, always ensure a descriptive `aria-label` or screen-reader-only text is present to indicate the action's purpose.
## 2025-05-15 - ARIA Labels on Search Inputs
**Learning:** Inputs that rely solely on `placeholder` attributes are poorly supported by screen readers. Form inputs that lack an explicitly associated visible `<label>` element must include a descriptive `aria-label` attribute (e.g., `aria-label="Search community"`) to ensure accessibility.
**Action:** Added `aria-label` to search inputs in `community.html`, `users.html`, `marketplace/index.html`, and `admin_matches.html`. In the future, actively look for and apply `aria-label` to form inputs and icon-only buttons that lack visible text labels.
## 2026-07-01 - ARIA Labels on Avatar Links and Icon Buttons
**Learning:** Anchor tags that wrap only images (like user avatars on the dashboard) and icon-only buttons (like delete/edit match) often lack context for screen readers. The image's `alt` text or a `title` attribute is insufficient for interactive elements.
**Action:** Always add descriptive `aria-label` attributes to anchor tags that only contain images, and to buttons that only contain icons (like emojis or FontAwesome icons) to clarify the action or destination.
## 2026-07-04 - CSS Dropdown Keyboard Accessibility
**Learning:** Pure CSS dropdowns that rely solely on `.dropdown:hover` are inaccessible to keyboard users because focusing on the trigger button with the `Tab` key does not trigger the `:hover` state, trapping the menu content.
**Action:** Always pair `.dropdown:hover .dropdown-content` with `.dropdown:focus-within .dropdown-content` to ensure the menu opens and remains open when any element inside the dropdown structure receives keyboard focus. Also ensure child links have a defined `:focus` state.
## 2026-07-06 - ARIA Expanded State on Dropdown Triggers
**Learning:** Script-driven toggles (like hamburger menus) often lack state indication for screen readers. While `aria-haspopup="true"` signals that a menu exists, screen reader users do not know whether the menu is currently open or closed without the `aria-expanded` attribute. Note that pure CSS dropdowns shouldn't have a static `aria-expanded="false"` because it won't update when the menu opens on hover/focus.
**Action:** For script-driven menus, ensure the JavaScript toggles the `aria-expanded` attribute between "true" and "false" when the menu's visibility changes, as demonstrated in `navbar.js`. Do not add static `aria-expanded="false"` to pure CSS dropdowns.
## 2026-07-24 - ARIA labels on Admin form inputs
**Learning:** Found that form inputs within administrative panels (like the "Merge Ghost" or "Delete User" forms in `admin.html`) often lacked proper `<label>` elements and `aria-label` attributes, relying entirely on visual placeholders. Since these tools are destructive or highly privileged, accessibility and clarity are paramount.
**Action:** Added explicit `aria-label` attributes to the inputs for "Real User ID", "Ghost Email", and "User ID or Email" to provide essential context for screen reader users and prevent reliance on transient placeholder text.
