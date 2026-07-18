## 2025-02-24 - [Fix DOM XSS in User Search]
**Vulnerability:** XSS vulnerability in `pickaladder/templates/tournament/view.html` where user-controlled API responses (`u.name` and `u.avatar`) were being directly interpolated into an HTML string assigned to `innerHTML`.
**Learning:** Raw string interpolation with `innerHTML` must be avoided or properly escaped, especially for data retrieved from an API like usernames or avatars. Using a basic `document.createElement('div').textContent = text` to escape HTML is unsafe for HTML attribute contexts (like `src="..."`) because it doesn't escape double or single quotes.
**Prevention:** Either construct elements safely using DOM APIs (`document.createElement`, `.textContent`, `.src`) or use a comprehensive regex-based escaping function that handles `&`, `<`, `>`, `"`, and `'`.

## 2024-07-18 - [Insecure Direct Object Reference (IDOR) on Action Routes]
**Vulnerability:** The `/send/<conversation_id>` route (an action route) lacked the authorization check that was present on the `/chat/<conversation_id>` route (the view route). A user could send a POST request with any `conversation_id` to send messages to conversations they were not a participant in.
**Learning:** Developers often remember to add authorization checks to view routes (because they fetch and display data) but forget to add the same checks to corresponding action routes (like sending a message or updating an object), assuming the UI flow protects the action.
**Prevention:** Always verify ownership or membership (authorization) on *both* view and action routes that use direct object references (like IDs). Do not rely on UI logic or hidden fields to protect endpoints.
