## 2024-07-23 - Prevent DOM-based XSS in Match History Row
**Vulnerability:** User dashboard match history row injected unsanitized user inputs (partner name, opponent name, tournament name) via template literals directly into the DOM using `insertAdjacentHTML` inside `renderMatchRow`. This allowed for potential DOM-based Cross-Site Scripting (XSS).
**Learning:** Client-side template generation that uses `innerHTML` or `insertAdjacentHTML` requires strict encoding of any data originating from the database, even if it appears to be simple "names" or "titles". These fields are user-controlled and can contain malicious payloads.
**Prevention:** Always use a robust HTML escaping function (like `escapeHtml`) to sanitize dynamic data before interpolating it into HTML strings on the client side. Ensure all user-controlled data points within the interpolated string are covered.

## 2025-02-24 - [Fix IDOR in Messaging Route]
**Vulnerability:** Insecure Direct Object Reference (IDOR) in the `pickaladder/messaging/routes.py` `send` route (`/send/<conversation_id>`). The route lacked authorization checks before processing a POST request to add a message to a conversation.
**Learning:** Action routes (POST/PUT/DELETE) that modify resources must explicitly verify that the authenticated user (`g.user.uid`) is authorized to perform the action on the target resource. Relying solely on the UI to hide or disable buttons is insufficient, as attackers can bypass the UI and send POST requests directly to the endpoints if they know or can guess the resource IDs.
**Prevention:** Always fetch the target resource in the route handler and verify that the current user's ID exists in the resource's permissions/participants list before executing the action.

## 2025-02-24 - [Fix DOM XSS in User Search]
**Vulnerability:** XSS vulnerability in `pickaladder/templates/tournament/view.html` where user-controlled API responses (`u.name` and `u.avatar`) were being directly interpolated into an HTML string assigned to `innerHTML`.
**Learning:** Raw string interpolation with `innerHTML` must be avoided or properly escaped, especially for data retrieved from an API like usernames or avatars. Using a basic `document.createElement('div').textContent = text` to escape HTML is unsafe for HTML attribute contexts (like `src="..."`) because it doesn't escape double or single quotes.
**Prevention:** Either construct elements safely using DOM APIs (`document.createElement`, `.textContent`, `.src`) or use a comprehensive regex-based escaping function that handles `&`, `<`, `>`, `"`, and `'`.

## 2024-05-18 - [DOM XSS in User Dashboard Match History]
**Vulnerability:** Found a DOM-based Cross-Site Scripting (XSS) vulnerability in `pickaladder/templates/user_dashboard.html`. The `renderMatchRow` function dynamically generates HTML strings for match rows by interpolating unescaped user-controlled inputs, such as `match.team1_name`, `match.team2_name`, `match.tournament_name`, and player display names (via `getDisplayName`). These HTML strings are then inserted into the DOM using `insertAdjacentHTML('beforeend', rowHtml)`, allowing arbitrary script execution if a malicious user creates a team or tournament with an XSS payload in its name.
**Learning:** Client-side rendering templates must sanitize or escape any user-generated content before inserting it into the DOM via methods that parse HTML (like `innerHTML` or `insertAdjacentHTML`). This codebase relies on raw template strings in JS for complex UI rendering which is prone to this anti-pattern.
**Prevention:** Implement and use a standard `escapeHtml` utility function in JavaScript when generating HTML strings that include user data. Alternatively, construct DOM elements securely using `document.createElement()` and `textContent` to avoid HTML parsing entirely.

## 2024-07-18 - [Insecure Direct Object Reference (IDOR) on Action Routes]
**Vulnerability:** The `/send/<conversation_id>` route (an action route) lacked the authorization check that was present on the `/chat/<conversation_id>` route (the view route). A user could send a POST request with any `conversation_id` to send messages to conversations they were not a participant in.
**Learning:** Developers often remember to add authorization checks to view routes (because they fetch and display data) but forget to add the same checks to corresponding action routes (like sending a message or updating an object), assuming the UI flow protects the action.
**Prevention:** Always verify ownership or membership (authorization) on *both* view and action routes that use direct object references (like IDs). Do not rely on UI logic or hidden fields to protect endpoints.
