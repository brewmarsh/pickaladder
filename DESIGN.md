# pickaladder Design Document

This document outlines the design of the pickaladder application.

## 1. Introduction

The pickaladder application is a web-based application that allows users to create and manage pickleball ladders.

## 2. System Architecture

The application is a monolithic web application built with Flask and PostgreSQL. It is containerized with Docker and deployed with docker-compose.

The Flask application is organized using a blueprint-based architecture. The application is divided into the following blueprints:

*   **auth**: Handles user authentication, including registration, login, logout, and password management.
*   **user**: Handles user-facing features, such as the user dashboard, user profiles, and friend management.
*   **admin**: Handles administrative features, such as user management, database management, and data generation.
*   **match**: Handles match-related features, such as creating and viewing matches, and the leaderboard.

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

The user interface is implemented with HTML, CSS, and JavaScript. The application uses the Bootstrap framework for styling. The templates and static files are located in the `pickaladder` package.
