# build environment for frontend
FROM node:16-alpine as frontend
WORKDIR /app
COPY frontend/ .
RUN npm ci
RUN npm run build

# build environment for backend
FROM python:3.9-slim as backend
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# production environment
FROM python:3.9-slim
WORKDIR /app
COPY --from=backend /app /app
COPY --from=backend /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages
COPY --from=frontend /app/build /app/static/build
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client
RUN pip install gunicorn
EXPOSE 80
CMD ["/usr/local/bin/gunicorn", "--bind", "0.0.0.0:80", "app:app"]
