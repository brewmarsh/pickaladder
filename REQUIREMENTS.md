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

*   **Type Checking:** Static type checking with `mypy` has been added to the CI/CD pipeline to improve code quality and catch type-related errors early.
*   **Comprehensive Testing:** Expand the test suite to include integration and end-to-end tests to ensure the application is well-tested and stable.
*   **Code Coverage:** Code coverage is now measured as part of the CI/CD pipeline to identify untested parts of the codebase.

### Documentation

*   **API Documentation:** Generate API documentation to make it easier for developers to understand and use the application's API.
*   **User Guide:** Create a comprehensive user guide to help users understand how to use the application.

### CI/CD

*   **Automated Deployments:** A CI/CD pipeline has been implemented using GitHub Actions to automate the deployment process and ensure that all changes are automatically tested and deployed.
*   **Infrastructure as Code:** Use a tool like Terraform to manage the application's infrastructure as code.
*   **Linting and Static Analysis:** The CI/CD pipeline includes steps for linting (`ruff`), static analysis (`mypy`), and security scanning (`bandit`) to ensure code quality and security.

### Configuration

*   **Configuration File:** The application should use a configuration file to store settings, rather than relying on environment variables.
*   **Logging:** The application should have a robust logging system that can be configured to log to different destinations (e.g., file, syslog, console).

### Documentation

*   **Code Comments:** The code should be well-commented to make it easier for other developers to understand.
*   **README.md:** The `README.md` file should be updated with more information about the project.

### Gameplay

*   **Match Formatting:** The formatting of the match page needs to be fixed.
*   **Match IDs:** Matches should have a large random ID instead of a static number for privacy reasons. Matches should only be allowed between friends.
*   **User Dashboard:** On the user's dashboard, we should show their DUPR rating.
*   **Ladder Ranking:** The average ladder ranking is determined by averaging their total points per game.
*   **Multiple Ladder Rankings:** We may add another ladder ranking later.
*   **Leaderboard:** The app should have a leaderboard page, showing the top 10 by ranking, including their average and number of games.
*   **Generate Random Matches:** We need a "generate 10 random matches" button on the admin page that would simulate 10 matches between friends in the database, randomly scoring from 0 to 11, or win by 2 if the lower score is 9 or 10.

### Gameplay

*   **Dark Mode:** Dark mode has been implemented correctly.
*   **Admin Page:** The admin page needs a more professional look, including the ability to customize the branding with a company logo and color scheme.
*   **Terms of Service:** The application should have a page where users can view the terms of service.
*   **Data Export:** Users should be able to export their data from the application.

## Known Issues

*   There is a race condition between the `web` and `db` containers that causes the application to time out on startup. This issue needs to be resolved.
*   There is a "Bad Request" error during installation that needs to be investigated and fixed.
*   The testing environment needs to be stabilized to allow for proper testing of the application.
