# Stage 1: Build the final image
FROM python:3.11-bullseye

WORKDIR /app

# Install curl, which is used by the Docker healthcheck.
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Copy the requirements file
COPY requirements.txt .

# Install the dependencies
RUN pip install git+https://github.com/pypa/pip.git@7daeda1cb53546615a8c75161028b8121321119e
RUN pip install --no-cache-dir setuptools==78.1.1
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root user
RUN useradd -m -u 1000 appuser

# Copy the application code with correct ownership
COPY --chown=appuser:appuser . .

# Copy the new redirecting index.html to the nginx root
COPY index.html /var/www/html/index.html

# Create the static directory in the nginx root and copy assets
RUN mkdir -p /var/www/html/static
COPY pickaladder/static/ /var/www/html/static/

# Expose the port
EXPOSE 27272

# Switch to the non-root user
USER appuser

# Run the application
CMD ["gunicorn", "--bind", "0.0.0.0:27272", "--timeout", "120", "app:app"]
