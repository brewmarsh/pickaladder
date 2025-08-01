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

## Build

The application is built using a multi-stage Docker build. The first stage builds the React frontend, and the second stage builds the final Python application, copying the built frontend assets from the first stage. This results in a small, optimized production image.

## Testing

To run the tests, use the following command:

```
make test
```

This will run the backend tests in a separate test database to avoid interfering with the development database.

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

To reset the development database, run the following command:

```
make reset-db
```

## Troubleshooting

If you are having issues with the database not being created correctly, you can try running the following command to remove the old database volume:

```
docker-compose down -v
```

After running this command, you can try running `make build` and `make up` again.