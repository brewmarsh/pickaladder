# Stage 1: Build the frontend
FROM node:16-bullseye as builder

WORKDIR /app/frontend

# Copy the frontend package files
COPY frontend/package.json frontend/package-lock.json ./

# Install frontend dependencies
RUN npm ci

# Copy the rest of the frontend source code
COPY frontend/ ./

# Build the frontend
RUN npm run build

# Stage 2: Build the final image
FROM python:3.9-bullseye

WORKDIR /app

# Install PostgreSQL client
RUN apt-get update && \
    apt-get install -y --no-install-recommends postgresql-client && \
    rm -rf /var/lib/apt/lists/*

# Copy the requirements file
COPY requirements.txt .

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Copy the built frontend from the builder stage
COPY --from=builder /app/frontend/build ./pickaladder/static/frontend

# Expose the port
EXPOSE 27272

# Run the application
CMD ["gunicorn", "--bind", "0.0.0.0:27272", "--timeout", "120", "app:app"]
