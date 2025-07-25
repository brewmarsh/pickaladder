# pickaladder Design Document

This document outlines the design of the pickaladder application.

## 1. Introduction

The pickaladder application is a web-based application that allows users to create and manage pickleball ladders.

## 2. System Architecture

The application is a monolithic web application built with Flask and PostgreSQL. The application is containerized with Docker and deployed with docker-compose.

## 3. Database Schema

The database schema is defined in the `init.sql` file. The schema consists of two tables: `users` and `friends`.

### 3.1. `users` table

The `users` table stores information about the users of the application. The table has the following columns:

*   `id`: A UUID that uniquely identifies each user.
*   `username`: The user's username.
*   `password`: The user's hashed password.
*   `email`: The user's email address.
*   `name`: The user's name.
*   `dupr_rating`: The user's DUPR rating.
*   `is_admin`: A boolean that indicates whether the user is an administrator.
*   `profile_picture`: The user's profile picture, stored as a blob.
*   `profile_picture_thumbnail`: A thumbnail of the user's profile picture, stored as a blob.
*   `dark_mode`: A boolean that indicates whether the user has enabled dark mode.

### 3.2. `friends` table

The `friends` table stores information about the friendships between users. The table has the following columns:

*   `user_id`: The ID of the user who initiated the friendship.
*   `friend_id`: The ID of the user who received the friendship.
*   `status`: The status of the friendship. The status can be `pending` or `accepted`.

## 4. Application Logic

The application logic is implemented in the `app.py` file. The file contains the following routes:

*   `/`: The home page.
*   `/install`: The installation page.
*   `/login`: The login page.
*   `/logout`: The logout route.
*   `/register`: The registration page.
*   `/dashboard`: The user dashboard.
*   `/users`: The users page.
*   `/add_friend/<friend_id>`: The route to add a friend.
*   `/accept_friend_request/<friend_id>`: The route to accept a friend request.
*   `/decline_friend_request/<friend_id>`: The route to decline a friend request.
*   `/admin`: The admin page.
*   `/admin/reset_db`: The route to reset the database.
*   `/admin/reset-admin`: The route to reset the admin account.
*   `/admin/delete_user/<user_id>`: The route to delete a user.
*   `/admin/promote_user/<user_id>`: The route to promote a user.
*   `/admin/reset_password/<user_id>`: The route to reset a user's password.
*   `/admin/generate_users`: The route to generate random users.
*   `/forgot_password`: The forgot password page.
*   `/reset_password`: The reset password page.
*   `/change_password`: The change password page.
*   `/profile_picture/<user_id>`: The route to serve a user's profile picture.
*   `/profile_picture_thumbnail/<user_id>`: The route to serve a user's profile picture thumbnail.
*   `/update_profile`: The route to update a user's profile.
*   `/verify_email/<email>`: The route to verify a user's email address.
*   `/friends`: The friends page.
*   `/users/<user_id>`: The route to view a user's profile.
*   `/admin/friend_graph`: The route to view a visual graph of friend connections.

## 5. User Interface

The user interface is implemented with HTML, CSS, and JavaScript. The application uses the Bootstrap framework for styling.

## 6. Future Enhancements

The following enhancements are planned for the future:

*   **Match functionality:** The match functionality will be re-implemented.
*   **API:** An API will be created to allow third-party applications to interact with the application.
*   **Real-time updates:** The application will be updated to use WebSockets for real-time updates.
