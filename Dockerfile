# Use the official Python image.
FROM python:3.9-bullseye

# Set the working directory.
WORKDIR /app

# Copy the requirements file.
COPY requirements.txt .

# Install the dependencies.
RUN pip install --no-cache-dir -r requirements.txt

# Verify that the dependencies are installed.
RUN pip list

# Copy the rest of the application code.
COPY . .


# Install PostgreSQL client.
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client

# Expose the port.
EXPOSE 27272

# Run the application.
CMD ["gunicorn", "--bind", "0.0.0.0:27272", "app:app"]
