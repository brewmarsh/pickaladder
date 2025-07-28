## Agent Instructions

This document provides instructions for agents working on the pickaladder application.

### System Decomposition

The pickaladder application is a monolithic Flask application. To facilitate parallel development, the application can be conceptually broken down into the following components:

*   **Frontend:** The user interface, implemented with HTML, CSS, and JavaScript. The frontend is located in the `templates` and `static` directories.
*   **Backend:** The application logic, implemented in Python with Flask. The main application file is `app.py`.
*   **Database:** The PostgreSQL database. The schema is defined in `init.sql`.

### Working on Components

*   **Frontend Agents:** Frontend agents should focus on the `templates` and `static` directories. They should have expertise in HTML, CSS, and JavaScript.
*   **Backend Agents:** Backend agents should focus on `app.py` and other Python files. They should have expertise in Python, Flask, and PostgreSQL.
*   **Database Agents:** Database agents should focus on `init.sql` and other database-related files. They should have expertise in PostgreSQL.

### Interface Documentation

The interface between the frontend, backend, and database is not formally documented. However, the following conventions are used:

*   The backend exposes a set of routes that are called by the frontend. These routes are defined in `app.py`.
*   The backend interacts with the database using the `psycopg2` library. The database queries are embedded in the Python code.

To improve the development process, it is recommended to create a formal API documentation that specifies the routes, request/response formats, and data models. This will help to decouple the frontend and backend and allow for independent development and testing.
