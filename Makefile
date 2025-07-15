build:
	docker-compose down -v --remove-orphans
	docker-compose up --build -d

up:
	docker-compose up -d
