# pickaladder Application Requirements

This document outlines the requirements for the pickaladder application.

## Functional Requirements

### User Management
*   **User Registration:** Users can create an account with a username, password, email address, and name.
*   **Email Verification:** Email verification can be enforced by an administrator. When enabled, users must verify their email address before they can log in. This setting is disabled by default.
*   **User Login:** Users can log in with their username and password.
*   **Password Reset:** Users can reset their password if they forget it.
*   **Profile Updates:** Users can update their DUPR rating, password, and profile picture from their dashboard.

### Friend Management
*   **Find Friends:** Users can find other users to be friends with.
*   **Add Friends:** Users can add other users as friends.
*   **View Friends:** Users can view a list of their friends.
*   **Friends of Friends:** Users can see a list of "friends of friends" to get recommendations for new friends.
*   **View Friend Profile:** Users can view a friend's profile.

### Gameplay
*   **Match Creation:** Users can create matches with their friends.
*   **Match Viewing:** Users can view the details of a match, including an emphasized icon for the winner and each player's win/loss record. The player's icon and username are also clickable links to their profile page.
*   **Leaderboard:** The application has a leaderboard that shows the top 10 players by average score.
*   **Match History:** The user profile page displays a history of the user's matches. The winning score is bolded, and each match is a clickable link to the match details page.

### Admin Functionality
*   **Admin Panel:** Admin users have access to an admin panel.
*   **User Management:** Admins can delete users, promote users to admins, reset user passwords, and manually verify a user's email address.
*   **Settings Management:** Admins can enable or disable the requirement for email verification from the admin panel.
*   **Database Management:** Admins can reset the database.
*   **Data Generation:** Admins can generate random users, matches, and groups for testing purposes.

## Non-Functional Requirements

### Architecture
*   **Monolithic Application:** The application is a monolithic web application built with Flask and PostgreSQL.
*   **Containerized:** The application is containerized with Docker and deployed with docker-compose.
*   **Blueprint-based:** The Flask application is organized using a blueprint-based structure.

### Database
*   **Database:** The application uses a PostgreSQL database.
*   **Connection Pooling:** The application uses a connection pool to manage database connections.
*   **Database Initialization:** The database is automatically initialized and migrated when the application starts.

### Security
*   **UUIDs:** User and match IDs are UUIDs to enhance privacy.
*   **Password Hashing:** Passwords are securely hashed using `pbkdf2:sha256` with 150,000 iterations. The application also includes a mechanism to re-hash the passwords of existing users on the fly when they log in.

### User Interface
*   **Modern Design:** The application has a modern, clean, and responsive user interface with a Google-inspired design.
*   **Custom Styling:** The application uses a custom stylesheet and does not depend on any external CSS frameworks like Bootstrap.
*   **Login Page:** The login page does not show a redundant "Please log in to access this page." message or a "LOGIN" button in the navigation bar.

### Code Quality
*   **Linting:** The project uses `ruff` for linting and code formatting.
*   **Testing:** The project has a basic test suite.

## Future Enhancements

### Usability Improvements
*   **Real-time Updates:** The application currently requires a page reload to see updates. Implementing real-time updates using WebSockets would provide a much better user experience. For example, the leaderboard could update in real-time as matches are completed.
*   **Improved User Profiles:** User profiles could be enhanced to include more information, such as a user's match history, win/loss record, and a short bio.
*   **Friend Request Notifications:** When a user receives a friend request, they should receive a notification. This could be an in-app notification or an email.
*   **Match Confirmation:** When a match is recorded, both players should be required to confirm the score. This would help prevent disputes and ensure the accuracy of match results.

### New User Features
*   **Match Scheduling:** Users should be able to schedule matches with other players. This would involve selecting a date, time, and location for the match.
*   **Double Matches:** The current application only supports singles matches. Adding support for doubles matches would be a valuable feature for many players.
*   **Player Statistics:** Users should be able to view detailed statistics about their own play, such as their win/loss record against specific opponents, their performance over time, and other metrics.
*   **Find a Partner:** A feature that allows users to find other players of a similar skill level to play with would be a great addition.
*   **Social Sharing:** Users should be able to share their match results and other achievements on social media.
*   **Match Location:** Users should be able to optionally record the location of a match. This could be a simple text field or integrated with a mapping service. This would be useful for tracking where matches are played and for facilities to see which courts are being used.

### Manager Features
*   **Tournament Brackets:** The application should support the creation and management of tournament brackets. This would include single-elimination, double-elimination, and round-robin formats.
*   **Facility Management:** Managers should be able to manage facility information, such as court availability and hours of operation.
*   **Event Registration:** The application should allow users to register for events and tournaments. This would include collecting registration fees and managing participant lists.
*   **Announcements:** Managers should be able to send announcements to all participants in an event or to all users of the application.
*   **Reporting:** The application should provide detailed reports on event participation, match results, and other key metrics. This would be useful for analyzing the success of events and for planning future ones.

### Security
*   **Input Validation:** Implement robust input validation on all user-supplied data.
*   **Password Policies:** Enforce strong password policies.
*   **Session Management:** Implement secure session management practices.
*   **Rate Limiting:** Implement rate limiting on sensitive endpoints.

### Quality
*   **Type Checking:** Add static type checking with `mypy`.
*   **Comprehensive Testing:** Expand the test suite to include integration and end-to-end tests.
*   **Code Coverage:** Measure code coverage to identify untested parts of the codebase.

### Documentation
*   **API Documentation:** Generate API documentation.
*   **User Guide:** Create a comprehensive user guide.

### CI/CD
*   **Automated Deployments:** Implement a CI/CD pipeline for automated testing and deployment.
*   **Infrastructure as Code:** Use a tool like Terraform to manage infrastructure as code.

### Configuration
*   **Configuration File:** Use a configuration file instead of environment variables for all settings.
*   **Logging:** Implement a more robust and configurable logging system.

### Other Features
*   **Multiple Ladder Rankings:** Add support for multiple ladder ranking systems.
*   **Customizable Branding:** Allow admins to customize the branding of the admin page.
*   **Terms of Service:** Add a terms of service page.
*   **Data Export:** Allow users to export their data.

## Known Issues

This section documents some of the known issues in the application.

*   **"Method Not Allowed" on root page login:** The root URL `/` is mapped to the login page, but it does not accept POST requests. This has been fixed by allowing POST requests on the root URL.
*   **"Method Not Allowed" on friend requests:** The buttons for accepting and declining friend requests were implemented as links, which send GET requests to a POST-only route. This has been fixed by replacing the links with forms that submit POST requests.
*   **CSRF error on friend requests:** The forms for accepting and declining friend requests were missing the CSRF token. This has been fixed by adding the CSRF token to the forms.

### Deeper Feature Suggestions

Based on a more in-depth review of the codebase, here are some more detailed feature suggestions.

#### Usability Improvements
*   **Autocomplete for User Search:** In the user search and "Create Match" opponent selection, implement an autocomplete feature to make it easier to find users, especially in a system with many users.
*   **Interactive Leaderboard:** The leaderboard could be made more interactive. For example, allowing users to see their own rank even if they are not in the top 10, and showing how many places they have moved up or down since the last time they checked.
*   **Dashboard Feed:** The user dashboard could be enhanced to show a "feed" of recent activity from their friends, such as recently played matches.

#### New User Features
*   **Advanced Ranking System:** Implement a more advanced ranking system like Elo or Glicko-2. These systems are better at predicting match outcomes and provide a more accurate measure of a player's skill level. This would also allow for features like predicting the outcome of a match before it's played.
*   **Public Profile URLs:** Allow users to have a public profile URL that they can share with others, even those who are not registered on the site. This could be an optional feature that users can enable or disable.
*   **Match History Charts:** On a user's profile, display charts and graphs to visualize their match history, such as their win/loss ratio over time, or their performance against different opponents.
*   **Achievements/Badges:** Add a system of achievements or badges that users can earn for reaching certain milestones (e.g., "Played 10 matches," "First win," "On a winning streak").

#### Manager Features
*   **Multiple Ladder Types:** Allow facility managers to create and manage different types of ladders, such as singles, doubles, mixed doubles, age-based ladders, or skill-level-based ladders (e.g., 3.0-3.5, 4.0-4.5).
*   **Court Reservation System:** Integrate a court reservation system. This would allow managers to define the courts available at their facility and allow users to book courts for their matches.
*   **Event-specific Leaderboards:** For tournaments or leagues, create separate leaderboards that are specific to that event, in addition to the overall site-wide leaderboard.
*   **Broadcast Messaging:** Give managers the ability to send broadcast messages to all participants of a specific tournament or league, or to all users who have played at their facility. This could be used for announcements, updates, or promotions.
