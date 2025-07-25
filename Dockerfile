# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN apt-get update --allow-insecure-repositories && apt-get install -y postgresql-client && apt-get clean
RUN pip install --no-cache-dir -r requirements.txt

# Make port 27272 available to the world outside this container
EXPOSE 27272

# Define environment variable
ENV NAME World

# Run app.py when the container launches
CMD ["gunicorn", "--bind", "0.0.0.0:27272", "app:app"]
