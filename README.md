[![CI](https://github.com/brewmarsh/pickaladder/actions/workflows/ci.yml/badge.svg)](https://github.com/brewmarsh/pickaladder/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/brewmarsh/pickaladder/branch/main/graph/badge.svg)](https://codecov.io/gh/brewmarsh/pickaladder)
[![GitHub License](https://img.shields.io/github/license/brewmarsh/pickaladder)](https://github.com/brewmarsh/pickaladder/blob/main/LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.9-blue.svg)](https://www.python.org/downloads/release/python-390/)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Trivy Scan](https://img.shields.io/github/actions/workflow/status/brewmarsh/pickaladder/ci.yml?label=trivy&logo=trivy)](https://github.com/brewmarsh/pickaladder/actions/workflows/ci.yml)

# 🥒 pickaladder 🥇

A modern web application for managing pickleball ladders, leagues, and tournaments! 🏆

## ✨ Features

`pickaladder` is packed with features to make managing and participating in pickleball ladders a breeze.

### 👤 User & Profile Management
*   **Easy Registration:** Simple sign-up process for new players.
*   **Email Verification:** Optional, admin-enforced email verification for new accounts.
*   **Secure Login & Password Reset:** Standard, secure authentication with a "forgot password" flow.
*   **Customizable Profiles:** Update your name, DUPR rating, and upload a custom profile picture.
*   **Personalized Dashboard:** A central hub to view your stats, recent matches, and friend activity.
*   **Dark Mode:** Switch to a sleek dark theme for comfortable viewing.

### 🧑‍🤝‍🧑 Social & Friends
*   **Find Players:** Search for other users in the system.
*   **Friend System:** Add friends to easily create matches and track your connections.
*   **Friend Recommendations:** Discover new players with a "Friends of Friends" suggestion list.
*   **View Profiles:** See other players' stats, match history, and friends.

### 👨‍👩‍👧‍👦 Groups & Leagues
*   **Create & Join Groups:** Form public or private groups for your club, league, or friends.
*   **Group Profiles:** Give your group a name, description, and profile picture.
*   **Invite-Only:** Invite your friends to join your private groups.
*   **Group Leaderboards:** Each group has its own leaderboard to track rankings internally.

### 🏓 Gameplay & Matches
*   **Record Matches:** Easily record match scores against your friends.
*   **Detailed Match View:** See a breakdown of each match, with the winner's icon emphasized.
*   **Player Records:** Automatically calculated win/loss records for every player.
*   **Global Leaderboard:** See how you stack up against the top 10 players on the site.
*   **Match History:** Your profile features a full history of your played matches.

### 👑 Admin Panel
*   **Full User Management:** Admins can delete users, promote new admins, reset user passwords, and manually verify emails.
*   **Site Settings:** Toggle application-wide settings, like requiring email verification.
*   **Test Data Generation:** Populate the site with randomly generated users and matches for testing.
*   **Database Reset:** A one-click option to reset the development database.

## 🚀 Getting Started

To get the application running locally, you'll need [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/) installed.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/pickaladder.git
    cd pickaladder
    ```

2.  **Start the application:**
    ```bash
    make up
    ```
    This command will build the Docker containers, start the application and database, and run any necessary database migrations.

3.  **Access the application:**
    Open your web browser and navigate to `http://localhost:27272`.

**Note:** The very first user to register will automatically be granted administrator privileges.

## 🛠️ Development

### Running Tests
To run the backend test suite, use the following command. Make sure the application is already running with `make up`.
```bash
make test
```

### Resetting the Database
To completely wipe the development database, run:
```bash
make reset-db
```

## 🔧 Troubleshooting

If you encounter issues with the database, you can remove the old database volume by running:
```bash
docker-compose down -v
```
After running this, you can try starting the application again with `make up`.
