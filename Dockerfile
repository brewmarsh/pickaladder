# Stage 1: Build the final image
FROM python:3.11-bullseye

WORKDIR /app

# Install PostgreSQL client
RUN apt-get update && \
    apt-get install -y --no-install-recommends postgresql-client && \
    rm -rf /var/lib/apt/lists/*

# Copy the requirements file
COPY requirements.txt .

# Install the dependencies
RUN pip install git+https://github.com/pypa/pip.git@f2b92314da012b9fffa36b3f3e67748a37ef464a
RUN pip install --no-cache-dir setuptools==78.1.1
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Copy the new redirecting index.html to the nginx root
COPY index.html /var/www/html/index.html

# Create the static directory in the nginx root and copy assets
RUN mkdir -p /var/www/html/static
COPY pickaladder/static/ /var/www/html/static/

# Expose the port
EXPOSE 27272

# Run the application
CMD ["gunicorn", "--bind", "0.0.0.0:27272", "--timeout", "120", "app:app"]