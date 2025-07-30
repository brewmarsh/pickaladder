build:
	docker compose down -v --remove-orphans
	docker compose up --build -d

up:
	docker compose up -d

test:
	docker compose -f docker-compose.yml -f docker-compose.test.yml exec web python -m unittest discover tests

reset-db:
	docker compose exec db psql -U user -d pickaladder -c "DROP TABLE IF EXISTS friends, matches, users CASCADE;"

migrate:
	docker compose exec -T db psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -f /migrations/1_add_dark_mode_column.sql
