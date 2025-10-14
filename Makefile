build:
	docker compose down -v --remove-orphans
	docker compose up --build -d

up:
	docker compose up -d

test:
	docker compose -f docker-compose.yml -f docker-compose.test.yml exec web sh -c "python -m unittest discover tests"

coverage:
	docker compose -f docker-compose.yml -f docker-compose.test.yml exec web sh -c "until pg_isready -h db -p 5432 -U user; do sleep 2; done && coverage run -m unittest discover tests"

reset-db:
	docker compose exec db psql -U $$POSTGRES_USER -d $$POSTGRES_DB -c "DROP TABLE IF EXISTS friends, matches, users CASCADE;"

migrate:
	docker compose exec web python migrate.py
