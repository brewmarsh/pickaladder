# Use the official Python image.
FROM python:3.9-slim

# Set the working directory.
WORKDIR /app

# Copy the requirements file.
COPY requirements.txt .

# Install the dependencies.
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code.
COPY . .

# Install Node.js and build the frontend.
RUN apt-get update && \
    apt-get install -y --no-install-recommends nodejs npm && \
    npm ci --prefix frontend && \
    npm run build --prefix frontend && \
    apt-get purge -y --auto-remove nodejs npm && \
    rm -rf /var/lib/apt/lists/*

# Install PostgreSQL client.
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client

# Expose the port.
EXPOSE 80

# Run the application.
CMD ["/usr/local/bin/gunicorn", "--bind", "0.0.0.0:80", "app:app"]
