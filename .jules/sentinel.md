## 2025-02-24 - [Fix DOM XSS in User Search]
**Vulnerability:** XSS vulnerability in `pickaladder/templates/tournament/view.html` where user-controlled API responses (`u.name` and `u.avatar`) were being directly interpolated into an HTML string assigned to `innerHTML`.
**Learning:** Raw string interpolation with `innerHTML` must be avoided or properly escaped, especially for data retrieved from an API like usernames or avatars. Using a basic `document.createElement('div').textContent = text` to escape HTML is unsafe for HTML attribute contexts (like `src="..."`) because it doesn't escape double or single quotes.
**Prevention:** Either construct elements safely using DOM APIs (`document.createElement`, `.textContent`, `.src`) or use a comprehensive regex-based escaping function that handles `&`, `<`, `>`, `"`, and `'`.
## 2025-02-25 - [Fix IDOR in Messaging Route]
**Vulnerability:** Insecure Direct Object Reference (IDOR) / Missing Authorization in the `/send/<conversation_id>` endpoint. Any authenticated user could send a POST request with any `conversation_id` and have the message appended to that conversation, bypassing UI protections.
**Learning:** Route-level validation is critical for state-modifying actions (POST/PUT/DELETE). Relying on the UI to not display a "Send" button is insufficient.
**Prevention:** Always verify `g.user.uid` against the target resource's access control list (e.g., the `participants` array in the conversation document) directly inside the route handler before performing the action.
