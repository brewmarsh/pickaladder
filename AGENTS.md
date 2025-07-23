# pickaladder Application Requirements

This document outlines the requirements that have been implemented for the pickaladder application.

## Functional Requirements

### User Management

*   **User Registration:** Users can create an account with a username, password, email address, and name. The first user to register will be an admin.
*   **User Login:** Users can log in with their username and password.
*   **Password Reset:** Users can reset their password if they forget it.
*   **Profile Updates:** Users can update their DUPR rating, password, and profile picture from their dashboard.

### Friend Management

*   **Find Friends:** Users can find other users to be friends with.
*   **Add Friends:** Users can add other users as friends. A toast message will be displayed to confirm that the request has been sent.
*   **View Friends:** Users can view a list of their friends on their dashboard.
*   **Friends of Friends:** Users can see a list of "friends of friends" to get recommendations for new friends.

### Admin Functionality

*   **Admin Panel:** Admin users have access to an admin panel where they can manage the application.
*   **Reset Database:** Admin users can reset the user database from the admin panel.
*   **Reset Admin:** Admin users can reset the admin account to the first user in the database.
*   **Generate Users:** Admin users can generate 10 random users with human-like names. The generated users are displayed on a separate page. This function will not create users that already exist.
*   **Delete Users:** Admin users can delete users from the user database. The application will also automatically delete any friendships associated with the deleted user. A toast message will be displayed to confirm the deletion.
*   **Promote Users:** Admin users can promote other users to administrators.
*   **Reset Passwords:** Admin users can reset user passwords. The new password will be sent to the user's email address.

### User Profile

*   **Dark Mode:** Users can enable or disable dark mode from their dashboard.

### Onboarding Flow

*   **Welcome Screen:** New users are greeted with a welcome screen that explains the application and the installation process.
*   **Admin Registration:** The first user to register is prompted to create an admin account.

## Non-Functional Requirements

### Reliability

*   **Idempotency:** Database operations are idempotent to prevent duplicate entries and other inconsistencies.
*   **Error Handling:** The application will now handle database errors more gracefully, displaying a custom error page with a link back to the dashboard instead of crashing. This applies to both user deletion and profile updates.

### Quality

*   **Code Quality:** The project uses `ruff` for linting and code formatting to maintain a consistent code style.
*   **Testing:** The project has a basic test suite to ensure the core functionality of the application is working correctly.

### Security

*   **UUIDs:** User and match IDs are now UUIDs to enhance privacy and prevent sequential ID guessing.

### UI/UX

*   **Dashboard:** The password field has been removed from the "Update Profile" form on the dashboard.
*   **Match Page:** The match page formatting has been reviewed and confirmed to be correct.

### Database

*   **Reset Database:** The database can be reset by running `make reset-db`. This will drop all tables and recreate them based on the `init.sql` file.
*   **Database Initialization:** The database is automatically initialized with the correct schema when the application is started. To force a re-initialization, run `make build`.

### Technical Requirements

*   **Database:** The application uses a PostgreSQL database.
*   **File Uploads:** Profile pictures are uploaded to the `static/uploads` directory. The application only accepts `.png`, `.jpg`, `.jpeg`, and `.gif` files.

## Known Issues

*   There is a race condition between the `web` and `db` containers that causes the application to time out on startup. This issue needs to be resolved.

## Future Enhancements

### Security

*   **Input Validation:** Implement robust input validation on all user-supplied data to prevent common vulnerabilities such as XSS and SQL injection.
*   **Password Policies:** Enforce strong password policies, including minimum length and complexity requirements.
*   **Session Management:** Implement secure session management practices, including session timeouts and protection against session fixation.
*   **Rate Limiting:** Implement rate limiting on authentication and other sensitive endpoints to prevent brute-force attacks.

### Quality

*   **Type Checking:** Introduce static type checking with a tool like `mypy` to improve code quality and catch type-related errors early.
*   **Comprehensive Testing:** Expand the test suite to include integration and end-to-end tests to ensure the application is well-tested and stable.
*   **Code Coverage:** Measure code coverage to identify untested parts of the codebase.

### Documentation

*   **API Documentation:** Generate API documentation to make it easier for developers to understand and use the application's API.
*   **User Guide:** Create a comprehensive user guide to help users understand how to use the application.

### CI/CD

*   **Automated Deployments:** Implement a CI/CD pipeline to automate the deployment process and ensure that all changes are automatically tested and deployed.
*   **Infrastructure as Code:** Use a tool like Terraform to manage the application's infrastructure as code.
