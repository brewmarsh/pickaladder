# Vocabulary Audit: 'ladder' occurrences in 'pickaladder'

Analysis of terms 'ladder', 'ladders', 'Ladder', and 'Ladders' across the codebase.

## 1. User-Facing UI Text
Occurrences are primarily found in landing pages and documentation to describe the product's purpose.
- **index.html**: "The best place to manage your pickleball ladders..."
- **welcome.html**: "This is a platform for pickleball ladders and tournaments."
- **login.html**: "Run Ladders" (feature list).
- **friends/index.html & community.html**: "It's like a ladder for pickleball, but with more losing." (Social share messages).
- **docs/REQUIREMENTS.md**: "Multiple Ladder Rankings", "Multiple Ladder Types".

## 2. Code Symbols
The term 'ladder' appears almost exclusively as part of the project/package name.
- **Package Name**: `pickaladder` is the root package. Every import statement (e.g., `from pickaladder.auth.decorators import login_required`) contains this string.
- **Constants**:
    - `DB_NAME = "pickaladder"` in `pickaladder/core/constants.py`.
    - `MAIL_DEFAULT_SENDER = "noreply@pickaladder.com"` in `pickaladder/config.py`.
- **Mock Data**: Found in `pickaladder/admin/routes.py` and `tests/`.

## 3. Database Schemas/References (KEEP)
These are critical infrastructure strings linked to Firebase.
- **Project ID**: `"pickaladder"` (used in initialization).
- **Auth Domain**: `"pickaladder.firebaseapp.com"`.
- **Storage Bucket**: `"pickaladder.firebasestorage.app"` and `"pickaladder.appspot.com"`.
- **Database Name**: `"pickaladder"`.

## 4. Branding
- **Logo Files**: `pickaladder_logo_64.png`, `pickaladder_logo_128.png`, etc., in `pickaladder/static/`.
- **Page Titles**: `<title>pickaladder - ...</title>` in `layout.html`.
- **Navbar/Footer**: Text labels "pickaladder" and copyright notices.
- **Manifest**: `"name": "pickaladder"` in `manifest.json`.

## High-Risk Areas for Renaming
- **Imports**: Renaming the `pickaladder` directory/package is a breaking change for the entire Python codebase. **Decision: Preserve 'pickaladder' branding and package name.**
- **Firebase Config**: The strings `"pickaladder"`, `"pickaladder.firebaseapp.com"`, and `"pickaladder.appspot.com"` in `layout.html` and `config.py` are hardcoded to the specific Firebase project. **Decision: DO NOT MODIFY.**
- **Static Assets**: Logo URLs in `layout.html` and `main.js` are hardcoded.

## Conclusion
The objective is to remove "ladder" as a *concept* (e.g., "join a ladder") and replace it with "groups" or "tournaments". We will **not** rename the package `pickaladder` or infrastructure strings, as these are branding and technical identifiers, not vocabulary that confuses users about the app's functionality.
