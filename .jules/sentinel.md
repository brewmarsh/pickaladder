## 2025-02-24 - [Fix IDOR in Messaging Route]
**Vulnerability:** Insecure Direct Object Reference (IDOR) in the `pickaladder/messaging/routes.py` `send` route (`/send/<conversation_id>`). The route lacked authorization checks before processing a POST request to add a message to a conversation.
**Learning:** Action routes (POST/PUT/DELETE) that modify resources must explicitly verify that the authenticated user (`g.user.uid`) is authorized to perform the action on the target resource. Relying solely on the UI to hide or disable buttons is insufficient, as attackers can bypass the UI and send POST requests directly to the endpoints if they know or can guess the resource IDs.
**Prevention:** Always fetch the target resource in the route handler and verify that the current user's ID exists in the resource's permissions/participants list before executing the action.

## 2025-02-24 - [Fix DOM XSS in User Search]
**Vulnerability:** XSS vulnerability in `pickaladder/templates/tournament/view.html` where user-controlled API responses (`u.name` and `u.avatar`) were being directly interpolated into an HTML string assigned to `innerHTML`.
**Learning:** Raw string interpolation with `innerHTML` must be avoided or properly escaped, especially for data retrieved from an API like usernames or avatars. Using a basic `document.createElement('div').textContent = text` to escape HTML is unsafe for HTML attribute contexts (like `src="..."`) because it doesn't escape double or single quotes.
**Prevention:** Either construct elements safely using DOM APIs (`document.createElement`, `.textContent`, `.src`) or use a comprehensive regex-based escaping function that handles `&`, `<`, `>`, `"`, and `'`.
