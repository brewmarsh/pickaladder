# pickaladder Application Requirements

This document outlines the requirements that have been implemented for the pickaladder application.

## User Management

*   **User Registration:** Users can create an account with a username, password, email address, and name. The first user to register will be an admin.
*   **User Login:** Users can log in with their username and password.
*   **Password Reset:** Users can reset their password if they forget it.
*   **Profile Updates:** Users can update their DUPR rating, password, and profile picture from their dashboard.

## Friend Management

*   **Find Friends:** Users can find other users to be friends with.
*   **Add Friends:** Users can add other users as friends.
*   **View Friends:** Users can view a list of their friends on their dashboard.
*   **Friends of Friends:** Users can see a list of "friends of friends" to get recommendations for new friends.

## Admin Functionality

*   **Admin Panel:** Admin users have access to an admin panel where they can manage the application.
*   **Reset Database:** Admin users can reset the user database from the admin panel.
*   **Reset Admin:** Admin users can reset the admin account to the first user in the database.
*   **Generate Users:** Admin users can generate 10 random users with human-like names. The generated users are displayed on a separate page. This function will not create users that already exist.
*   **Delete Users:** Admin users can delete users from the user database.
*   **Promote Users:** Admin users can promote other users to administrators.

## Database

*   **Reset Database:** The database can be reset by running `make reset-db`. This will drop all tables and recreate them based on the `init.sql` file.

## Error Handling

*   **Database Errors:** The application will now handle database errors more gracefully, displaying a user-friendly error page instead of crashing.

## User Profile

*   **Dark Mode:** Users can enable or disable dark mode from their dashboard.

## Onboarding Flow

*   **Welcome Screen:** New users are greeted with a welcome screen that explains the application and the installation process.
*   **Admin Registration:** The first user to register is prompted to create an admin account.

## Technical Requirements

*   **Database:** The application uses a PostgreSQL database.
*   **File Uploads:** Profile pictures are uploaded to the `static/uploads` directory. The application only accepts `.png`, `.jpg`, `.jpeg`, and `.gif` files.
*   **Database Initialization:** The database is automatically initialized with the correct schema when the application is started. To force a re-initialization, run `make build`.

## Known Issues

*   There is a race condition between the `web` and `db` containers that causes the application to time out on startup. This issue needs to be resolved.
