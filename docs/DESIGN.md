# pickaladder Design Document

This document outlines the design of the pickaladder application.

## 1. Introduction

The pickaladder application is a web-based application that allows users to create and manage pickleball ladders.

## 2. System Architecture

The application is a monolithic web application built with Flask and PostgreSQL. It is containerized with Docker and deployed with docker compose.

### 2.1. Application Architecture

The Flask application is organized using a blueprint-based architecture. The application is divided into the following blueprints:

*   **auth**: Handles user authentication, including registration, login, logout, and password management.
*   **user**: Handles user-facing features, such as the user dashboard, user profiles, and friend management.
*   **admin**: Handles administrative features, such as user management, database management, and data generation.
*   **match**: Handles match-related features, such as creating and viewing matches, and the leaderboard.

### 2.2. Build Process

The application is built using a multi-stage Docker build.
*   **Stage 1 (builder)**: This stage uses a `node` base image to build the React frontend. It copies the frontend code, installs dependencies, and runs the build script.
*   **Stage 2 (final)**: This stage uses a `python` base image. It copies the Python application code, installs the Python dependencies, and then copies the built frontend assets from the `builder` stage.

This approach results in a small, optimized production image that does not contain any of the build-time dependencies.

## 3. Database

### 3.1. Database Schema

The database schema is defined in the `init.sql` file and is versioned with migration scripts in the `migrations` directory. The schema consists of the following tables:

*   `users`: Stores user information.
*   `friends`: Stores friendship information.
*   `matches`: Stores match information.
*   `migrations`: Stores information about applied migrations.

The `users` table has the following columns:

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
*   `email_verified`: A boolean that indicates whether the user has verified their email address.

### 3.2. Database Connection Management

The application uses a `psycopg2` connection pool to manage database connections. The connection pool is initialized when the application starts, and connections are managed by the Flask application context.

## 4. Application Logic

The application logic is implemented in the `pickaladder` package. The application is divided into blueprints, each with its own `routes.py` file that contains the routes for that part of the application.

The application uses an application factory pattern (`create_app`) to create and configure the Flask application instance.

## 5. User Interface

The user interface is implemented with HTML, CSS, and JavaScript, following a modern, clean, and responsive design aesthetic inspired by Google's Material Design. The application uses a custom stylesheet for all its styling, ensuring a lightweight and consistent look and feel across all pages.

### 5.1. Design Philosophy

The UI design is guided by the following principles:

*   **Clarity:** The interface is designed to be intuitive and easy to navigate.
*   **Efficiency:** Users can accomplish tasks with a minimum number of actions.
*   **Consistency:** UI elements and layouts are consistent throughout the application.
*   **Simplicity:** The design is clean and uncluttered, with a focus on a great user experience.

### 5.2. Styling

All styling is handled by a custom CSS stylesheet located at `pickaladder/static/style.css`. The stylesheet uses CSS variables for colors, fonts, and other properties to ensure consistency and maintainability. The application does not use any external CSS frameworks like Bootstrap.

### 5.3. Templates

The application uses the Jinja2 templating engine. All pages extend a base layout template (`layout.html`) to ensure a consistent structure. The templates are located in the `pickaladder/templates` directory.

### 5.4. Key UI Features

*   **Match View:** The match view page provides a detailed look at a single match. It emphasizes the winner's profile picture with a border and a box-shadow, and fades the loser's icon to create a clear visual distinction. It also displays each player's win/loss record under their username. The user's icon and username are clickable links to their profile page.
*   **User Profile:** The user profile page includes a match history section. Each match in the history is a clickable link to the match details page, and the winning score is displayed in bold.
