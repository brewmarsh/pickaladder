build:
	docker compose down -v --remove-orphans
	docker compose up --build -d

up:
	docker compose up -d

test:
	docker compose -f docker-compose.yml -f docker-compose.test.yml exec web python -m unittest discover tests

reset-db:
	docker compose exec db psql -U postgres -d postgres -c "DROP TABLE IF EXISTS friends, matches, users CASCADE; CREATE TABLE users (id SERIAL PRIMARY KEY, username TEXT NOT NULL UNIQUE, password TEXT NOT NULL, email TEXT NOT NULL, name TEXT, dupr_rating NUMERIC(3, 2), is_admin BOOLEAN DEFAULT FALSE, profile_picture TEXT, dark_mode BOOLEAN DEFAULT FALSE); CREATE TABLE friends (user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, friend_id INTEGER REFERENCES users(id) ON DELETE CASCADE, status TEXT DEFAULT 'pending', PRIMARY KEY (user_id, friend_id)); CREATE TABLE matches (id SERIAL PRIMARY KEY, player1_id INTEGER REFERENCES users(id), player2_id INTEGER REFERENCES users(id), player1_score INTEGER, player2_score INTEGER, match_date DATE);"

migrate:
	docker compose exec -T db psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -f /migrations/1_add_dark_mode_column.sql
