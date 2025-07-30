# pickaladder API Documentation

This document describes the API for the pickaladder application.

## 1. Authentication

The API uses a session-based authentication mechanism. After a user logs in, a `user_id` is stored in the session. This `user_id` is used to authenticate subsequent requests.

## 2. Endpoints

### 2.1. User Management

#### `POST /register`

Registers a new user.

*   **Request Body:**
    *   `username` (string, required): The user's username.
    *   `password` (string, required): The user's password.
    *   `email` (string, required): The user's email address.
    *   `name` (string, required): The user's name.
    *   `dupr_rating` (float, optional): The user's DUPR rating.
*   **Response:**
    *   Redirects to the dashboard on success.
    *   Returns an error message on failure.

#### `POST /login`

Logs in a user.

*   **Request Body:**
    *   `username` (string, required): The user's username.
    *   `password` (string, required): The user's password.
*   **Response:**
    *   Redirects to the dashboard on success.
    *   Returns an error message on failure.

#### `GET /logout`

Logs out a user.

*   **Response:**
    *   Redirects to the index page.

### 2.2. Gameplay

#### `GET /leaderboard`

Returns the top 10 players by average score.

*   **Response:**
    *   A JSON object containing a list of players. Each player object has the following fields:
        *   `id` (string): The player's ID.
        *   `name` (string): The player's name.
        *   `avg_score` (float): The player's average score.
        *   `games_played` (integer): The number of games the player has played.

### 2.3. Admin

#### `GET /admin/generate_matches`

Generates 10 random matches between friends.

*   **Response:**
    *   Redirects to the admin page.

#### `GET /admin/friend_graph_data`

Returns the data for the friend graph.

*   **Response:**
    *   A JSON object with two keys: `nodes` and `edges`.
        *   `nodes` is a list of objects, each with an `id` and `label`.
        *   `edges` is a list of objects, each with a `from` and `to`.

## 3. Data Models

### 3.1. User

*   `id` (UUID): The user's ID.
*   `username` (string): The user's username.
*   `password` (string): The user's hashed password.
*   `email` (string): The user's email address.
*   `name` (string): The user's name.
*   `dupr_rating` (float): The user's DUPR rating.
*   `is_admin` (boolean): Whether the user is an admin.
*   `profile_picture` (bytea): The user's profile picture.
*   `profile_picture_thumbnail` (bytea): The user's profile picture thumbnail.
*   `dark_mode` (boolean): Whether the user has dark mode enabled.

### 3.2. Match

*   `id` (UUID): The match's ID.
*   `player1_id` (UUID): The ID of the first player.
*   `player2_id` (UUID): The ID of the second player.
*   `player1_score` (integer): The score of the first player.
*   `player2_score` (integer): The score of the second player.
*   `match_date` (date): The date the match was played.

### 3.3. Friend

*   `user_id` (UUID): The ID of the user who initiated the friendship.
*   `friend_id` (UUID): The ID of the user who received the friendship.
*   `status` (string): The status of the friendship (`pending` or `accepted`).
