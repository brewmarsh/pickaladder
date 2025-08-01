# pickaladder API Documentation

This document describes the API for the pickaladder application.

## 1. Authentication

The API uses a session-based authentication mechanism. After a user logs in, a `user_id` is stored in the session. This `user_id` is used to authenticate subsequent requests.

## 2. Endpoints

The application is divided into blueprints, and the endpoints are prefixed with the blueprint name.

### 2.1. Auth Blueprint (`/auth`)

#### `POST /auth/register`
Registers a new user.

*   **Request Body:** `username`, `password`, `email`, `name`, `dupr_rating`
*   **Response:** Redirects to the dashboard on success.

#### `POST /auth/login`
Logs in a user.

*   **Request Body:** `username`, `password`
*   **Response:** Redirects to the dashboard on success.

#### `GET /auth/logout`
Logs out a user.

*   **Response:** Redirects to the index page.

#### `GET /auth/verify_email/<email>`
Verifies a user's email address.

*   **Response:** Redirects to the login page.

### 2.2. User Blueprint (`/`)

#### `GET /dashboard`
Displays the user's dashboard.

#### `GET /users`
Displays a list of all users.

#### `GET /users/<user_id>`
Displays a user's profile.

#### `GET /friends`
Displays the user's friends and friend requests.

### 2.3. Match Blueprint (`/match`)

#### `GET /match/leaderboard`
Returns the top 10 players by average score.

*   **Response:** A rendered HTML page with the leaderboard.

#### `GET /match/<uuid:match_id>`
Displays the details of a match.

### 2.4. Admin Blueprint (`/admin`)

#### `GET /admin/generate_matches`
Generates 10 random matches between friends.

*   **Response:** Redirects to the admin page.

#### `GET /admin/friend_graph_data`
Returns the data for the friend graph.

*   **Response:** A JSON object with `nodes` and `edges`.

## 3. Data Models

### 3.1. User
*   `id` (UUID)
*   `username` (string)
*   `password` (string)
*   `email` (string)
*   `name` (string)
*   `dupr_rating` (float)
*   `is_admin` (boolean)
*   `profile_picture` (bytea)
*   `profile_picture_thumbnail` (bytea)
*   `dark_mode` (boolean)
*   `email_verified` (boolean)

### 3.2. Match
*   `id` (UUID)
*   `player1_id` (UUID)
*   `player2_id` (UUID)
*   `player1_score` (integer)
*   `player2_score` (integer)
*   `match_date` (date)

### 3.3. Friend
*   `user_id` (UUID)
*   `friend_id` (UUID)
*   `status` (string)
