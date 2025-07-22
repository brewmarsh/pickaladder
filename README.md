# pickaladder

A simple web application for managing pickleball ladders.

## Features

* User registration and login
* Friend management
* Match tracking
* Admin panel for user management

## Getting Started

To get started with the application, you will need to have Docker and Docker Compose installed.

1. Clone the repository
2. Run `make build` to build the Docker containers
3. Run `make up` to start the application
4. The application will be available at `http://localhost:27272`

## Admin

The first user to register will be an admin. The admin can access the admin panel at `/admin`.

The admin can:

* Reset the database
* Generate random users
* Reset the admin account
* Delete users
* Promote users to administrators
* Reset user passwords

### Database

To reset the database, run the following command:

```
make reset-db
```